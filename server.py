#!/usr/bin/env python3
"""
GenGame Server - Authoritative Server Implementation

This server runs the game simulation without graphics and broadcasts game state to clients.
"""

import socket
import threading
import time
import pickle
import os
import sys
import glob
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
import select

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from GameFolder.setup import setup_battle_arena




class GameServer:
    """
    Authoritative server that runs the game simulation and broadcasts state to clients.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 5555):
        self.host = host
        self.port = port
        self.running = False

        # Network setup
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((host, port))
        self.server_socket.listen(8)  # Max 8 players
        self.server_socket.setblocking(False)

        # Client management
        self.clients: Dict[str, socket.socket] = {}  # player_id -> socket
        self.client_addresses: Dict[str, Tuple[str, int]] = {}  # player_id -> (ip, port)
        self.input_queues: Dict[str, List] = defaultdict(list)  # player_id -> list of inputs
        self.last_input_ids: Dict[str, int] = {}  # player_id -> last processed input_id
        self.player_name_to_id: Dict[str, str] = {}  # requested_name -> assigned_player_id
        self.player_id_to_character: Dict[str, str] = {}  # assigned_player_id -> character_id

        # Game state
        self.arena = None
        self.tick_rate = 60  # 60 FPS simulation
        self.tick_interval = 1.0 / self.tick_rate
        self.last_tick_time = 0.0
        self.game_start_time = 0.0

        # File synchronization
        self.game_files = {}  # filename -> content
        self._load_game_files()

        print(f"Server initialized on {host}:{port}")

    def _load_game_files(self):
        """Load all Python files from GameFolder for synchronization."""
        game_folder = os.path.join(os.path.dirname(__file__), "GameFolder")
        for root, dirs, files in os.walk(game_folder):
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    rel_path = os.path.relpath(filepath, os.path.dirname(__file__))

                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        self.game_files[rel_path] = content
                        print(f"Loaded game file: {rel_path}")
                    except Exception as e:
                        print(f"Failed to load {rel_path}: {e}")

    def start(self):
        """Start the server."""
        self.running = True

        # Initialize the game arena using the centralized setup function
        # with headless mode enabled (no graphics rendering on server)
        self.arena = setup_battle_arena(width=1200, height=700, headless=True)
        
        # Assign network player IDs to the characters created by setup_battle_arena()
        # setup_battle_arena() creates Player1 and Player2 - we need to assign network IDs
        if len(self.arena.characters) >= 2:
            self.arena.characters[0].id = "player_0"  # First player
            self.arena.characters[1].id = "player_1"  # Second player
        else:
            print("Warning: setup_battle_arena() didn't create enough characters!")
        
        self.game_start_time = time.time()

        # Start network thread
        network_thread = threading.Thread(target=self._network_loop, daemon=True)
        network_thread.start()

        # Start game loop
        self._game_loop()

    def stop(self):
        """Stop the server."""
        self.running = False
        self.server_socket.close()
        for client_socket in self.clients.values():
            try:
                client_socket.close()
            except:
                pass
        print("Server stopped.")

    def _network_loop(self):
        """Handle network connections and client communication."""
        while self.running:
            try:
                # Check for new connections
                try:
                    client_socket, address = self.server_socket.accept()
                    self._handle_new_connection(client_socket, address)
                except BlockingIOError:
                    pass  # No new connections

                # Handle existing clients
                self._handle_client_messages()

                time.sleep(0.01)  # Small delay to prevent busy waiting

            except Exception as e:
                print(f"Network error: {e}")

    def _handle_new_connection(self, client_socket: socket.socket, address: Tuple[str, int]):
        """Handle a new client connection."""
        print(f"New connection from {address}")

        # Assign player ID
        player_id = f"player_{len(self.clients)}"
        self.clients[player_id] = client_socket
        self.client_addresses[player_id] = address
        client_socket.setblocking(False)

        # Send file synchronization data
        self._send_file_sync(player_id)

    def _send_file_sync(self, player_id: str):
        """Send game files to client for synchronization."""
        try:
            client_socket = self.clients[player_id]

            # Send file sync header
            sync_data = {
                'type': 'file_sync',
                'files': self.game_files
            }

            data = pickle.dumps(sync_data)
            # Send length first, then data
            length_bytes = len(data).to_bytes(4, byteorder='big')
            client_socket.send(length_bytes)
            client_socket.send(data)

            print(f"Sent file sync to {player_id}")

        except Exception as e:
            print(f"Failed to send file sync to {player_id}: {e}")

    def _handle_client_messages(self):
        """Receive and process messages from all clients."""
        sockets_to_check = list(self.clients.values())

        if not sockets_to_check:
            return

        try:
            readable, _, _ = select.select(sockets_to_check, [], [], 0.01)

            for client_socket in readable:
                try:
                    # Find player_id for this socket
                    player_id = None
                    for pid, sock in self.clients.items():
                        if sock == client_socket:
                            player_id = pid
                            break

                    if not player_id:
                        continue

                    # Receive message
                    length_bytes = client_socket.recv(4)
                    if not length_bytes:
                        # Client disconnected
                        self._handle_client_disconnect(player_id)
                        continue

                    message_length = int.from_bytes(length_bytes, byteorder='big')

                    # Receive the actual message
                    data = b''
                    while len(data) < message_length:
                        chunk = client_socket.recv(message_length - len(data))
                        if not chunk:
                            break
                        data += chunk

                    if len(data) == message_length:
                        message = pickle.loads(data)
                        self._process_client_message(player_id, message)

                except Exception as e:
                    # Client likely disconnected
                    self._handle_client_disconnect(player_id)
                    continue

        except Exception as e:
            print(f"Error handling client messages: {e}")

    def _handle_client_disconnect(self, player_id: str):
        """Handle client disconnection."""
        if player_id in self.clients:
            try:
                self.clients[player_id].close()
            except:
                pass
            del self.clients[player_id]
            del self.client_addresses[player_id]
            if player_id in self.input_queues:
                del self.input_queues[player_id]
            print(f"Client {player_id} disconnected")

    def _process_client_message(self, player_id: str, message: dict):
        """Process a message from a client."""
        msg_type = message.get('type', 'input')

        if msg_type == 'input':
            # Add to input queue
            self.input_queues[player_id].append(message)
        elif msg_type == 'file_sync_ack':
            # Client acknowledged file sync
            print(f"{player_id} acknowledged file sync")
        elif msg_type == 'player_name':
            # Client sent their requested player name
            requested_name = message.get('player_name')
            if requested_name:
                self.player_name_to_id[requested_name] = player_id
                # Map player_id to character_id
                character_id = "player_0" if requested_name == "Player1" else "player_1"
                self.player_id_to_character[player_id] = character_id

                # Send back the assigned character info
                response = {
                    'type': 'character_assignment',
                    'requested_name': requested_name,
                    'assigned_character': requested_name
                }
                data = pickle.dumps(response)
                length_bytes = len(data).to_bytes(4, byteorder='big')
                try:
                    self.clients[player_id].send(length_bytes + data)
                except:
                    pass
        elif msg_type == 'file_request':
            # Client requesting a file
            self._handle_file_request(player_id, message)
        elif msg_type == 'file_chunk':
            # Client sending a file chunk
            self._handle_file_chunk(player_id, message)
        elif msg_type == 'file_ack':
            # Client acknowledging file receipt
            success = message.get('success', True)
            error = message.get('error', '')
            if success:
                print(f"{player_id} successfully received file: {message['file_path']}")
            else:
                print(f"{player_id} failed to receive file {message['file_path']}: {error}")

    def _handle_file_request(self, player_id: str, message: dict):
        """Handle a file request from a client."""
        file_path = message.get('file_path')

        if not file_path:
            print(f"Invalid file request from {player_id}: no file_path")
            return

        # Security check: ensure the file is within allowed directories
        allowed_dirs = ['GameFolder', 'BASE_components']
        if not any(file_path.startswith(dir_name + '/') for dir_name in allowed_dirs):
            print(f"File request denied for {player_id}: {file_path} (not in allowed directories)")
            # Send error response
            response = {
                'type': 'file_complete',
                'file_path': file_path,
                'success': False,
                'error': 'Access denied'
            }
            self._send_message_to_client(player_id, response)
            return

        # Check if file exists
        full_path = os.path.join(os.path.dirname(__file__), file_path)
        full_path = os.path.abspath(full_path)

        # Security check: ensure it's within the project directory
        project_dir = os.path.abspath(os.path.dirname(__file__))
        if not full_path.startswith(project_dir):
            print(f"File request denied for {player_id}: {file_path} (outside project directory)")
            response = {
                'type': 'file_complete',
                'file_path': file_path,
                'success': False,
                'error': 'Access denied'
            }
            self._send_message_to_client(player_id, response)
            return

        if not os.path.exists(full_path):
            print(f"File not found for {player_id}: {file_path}")
            response = {
                'type': 'file_complete',
                'file_path': file_path,
                'success': False,
                'error': 'File not found'
            }
            self._send_message_to_client(player_id, response)
            return

        # Send file in chunks
        try:
            file_size = os.path.getsize(full_path)
            chunk_size = 64 * 1024  # 64KB chunks
            total_chunks = (file_size + chunk_size - 1) // chunk_size

            with open(full_path, 'rb') as f:
                for chunk_num in range(total_chunks):
                    chunk_data = f.read(chunk_size)

                    chunk_message = {
                        'type': 'file_chunk',
                        'file_path': file_path,
                        'chunk_num': chunk_num,
                        'total_chunks': total_chunks,
                        'data': chunk_data
                    }

                    self._send_message_to_client(player_id, chunk_message)

            print(f"Sent file {file_path} to {player_id} ({total_chunks} chunks)")

        except Exception as e:
            print(f"Failed to send file {file_path} to {player_id}: {e}")
            response = {
                'type': 'file_complete',
                'file_path': file_path,
                'success': False,
                'error': str(e)
            }
            self._send_message_to_client(player_id, response)

    def _handle_file_chunk(self, player_id: str, message: dict):
        """Handle a file chunk received from a client."""
        file_path = message.get('file_path')
        chunk_num = message.get('chunk_num')
        total_chunks = message.get('total_chunks')
        chunk_data = message.get('data')

        if not all([file_path, isinstance(chunk_num, int), isinstance(total_chunks, int), chunk_data]):
            print(f"Invalid file chunk from {player_id}")
            return

        # Initialize file transfer tracking if needed
        if not hasattr(self, 'client_file_transfers'):
            self.client_file_transfers = {}

        client_key = f"{player_id}:{file_path}"
        if client_key not in self.client_file_transfers:
            self.client_file_transfers[client_key] = {
                'chunks': {},
                'total_chunks': total_chunks,
                'received_chunks': 0
            }

        transfer = self.client_file_transfers[client_key]

        # Store chunk if not already received
        if chunk_num not in transfer['chunks']:
            transfer['chunks'][chunk_num] = chunk_data
            transfer['received_chunks'] += 1

        # Check if file is complete
        if transfer['received_chunks'] == total_chunks:
            self._assemble_client_file(player_id, file_path)

    def _assemble_client_file(self, player_id: str, file_path: str):
        """Assemble a complete file from client chunks."""
        client_key = f"{player_id}:{file_path}"
        transfer = self.client_file_transfers[client_key]

        try:
            # Security check: ensure the target path is safe
            allowed_dirs = ['uploads', 'temp']
            target_dir = allowed_dirs[0] if 'uploads' in allowed_dirs else 'temp'

            # Create target directory if it doesn't exist
            full_dir = os.path.join(os.path.dirname(__file__), target_dir)
            os.makedirs(full_dir, exist_ok=True)

            # Create safe filename
            safe_filename = os.path.basename(file_path).replace('..', '').replace('/', '_').replace('\\', '_')
            full_path = os.path.join(full_dir, f"{player_id}_{safe_filename}")

            # Write file by combining chunks in order
            with open(full_path, 'wb') as f:
                for chunk_num in range(transfer['total_chunks']):
                    if chunk_num in transfer['chunks']:
                        f.write(transfer['chunks'][chunk_num])
                    else:
                        raise ValueError(f"Missing chunk {chunk_num}")

            # Send success acknowledgment
            response = {
                'type': 'file_complete',
                'file_path': file_path,
                'success': True,
                'saved_path': full_path
            }
            self._send_message_to_client(player_id, response)

            print(f"Received and saved file from {player_id}: {full_path}")

        except Exception as e:
            print(f"Failed to assemble file from {player_id}: {e}")
            response = {
                'type': 'file_complete',
                'file_path': file_path,
                'success': False,
                'error': str(e)
            }
            self._send_message_to_client(player_id, response)

        finally:
            # Clean up transfer state
            if client_key in self.client_file_transfers:
                del self.client_file_transfers[client_key]

    def _send_message_to_client(self, player_id: str, message: dict):
        """Send a message to a specific client."""
        if player_id not in self.clients:
            return

        try:
            data = pickle.dumps(message)
            length_bytes = len(data).to_bytes(4, byteorder='big')
            self.clients[player_id].send(length_bytes + data)
        except Exception as e:
            print(f"Failed to send message to {player_id}: {e}")
            # Client might have disconnected
            self._remove_client(player_id)

    def _game_loop(self):
        """Main game simulation loop."""
        print("Starting game simulation...")

        while self.running:
            current_time = time.time()

            # Fixed timestep game update
            if current_time - self.last_tick_time >= self.tick_interval:
                self._update_simulation(self.tick_interval)
                self._broadcast_game_state()
                self.last_tick_time = current_time

            # Sleep to prevent busy waiting
            time.sleep(0.001)

    def _update_simulation(self, delta_time: float):
        """Update the game simulation."""
        if not self.arena:
            return

        # Process all queued inputs
        for player_id, inputs in self.input_queues.items():
            for input_data in inputs:
                self._apply_player_input(player_id, input_data)
            # Clear processed inputs
            inputs.clear()

        # Update arena (physics, collisions, etc.)
        self.arena.update(delta_time)

    def _apply_player_input(self, player_id: str, input_data: dict):
        """Apply input from a client to the corresponding character."""
        # Track input ID for client-side prediction reconciliation
        input_id = input_data.get('input_id', 0)
        if input_id > self.last_input_ids.get(player_id, 0):
            self.last_input_ids[player_id] = input_id

        # Find the character controlled by this player (based on requested character)
        character_id = self.player_id_to_character.get(player_id, player_id)  # fallback to player_id

        character = None
        for char in self.arena.characters:
            if char.id == character_id:
                character = char
                break

        if not character:
            return

        # Update arena mouse position for TronProjectile tracking
        if 'mouse_pos' in input_data:
            self.arena.last_mouse_world_pos = input_data['mouse_pos']

        # Apply movement
        if 'movement' in input_data:
            direction = input_data['movement']
            character.move(direction, self.arena.platforms)

        # Apply shooting
        if 'shoot' in input_data:
            target_pos = input_data['shoot']
            projectiles = character.shoot(target_pos)
            if projectiles:
                # Handle both single projectile and list of projectiles
                if isinstance(projectiles, list):
                    self.arena.projectiles.extend(projectiles)
                else:
                    self.arena.projectiles.append(projectiles)

        # Apply secondary fire
        if 'secondary_fire' in input_data:
            target_pos = input_data['secondary_fire']
            projectiles = character.secondary_fire(target_pos)
            if projectiles:
                # Handle both single projectile and list of projectiles
                if isinstance(projectiles, list):
                    self.arena.projectiles.extend(projectiles)
                else:
                    self.arena.projectiles.append(projectiles)

        # Apply special fire
        if 'special_fire' in input_data:
            target_pos = input_data['special_fire']
            is_holding = input_data.get('special_fire_holding', False)
            projectiles = character.special_fire(target_pos, is_holding)
            if projectiles:
                # Handle both single projectile and list of projectiles
                if isinstance(projectiles, list):
                    self.arena.projectiles.extend(projectiles)
                else:
                    self.arena.projectiles.append(projectiles)

        # Apply weapon drop
        if input_data.get('drop_weapon', False):
            dropped_weapon = character.drop_weapon()
            if dropped_weapon:
                self.arena.spawn_weapon(dropped_weapon)

    def _broadcast_game_state(self):
        """Broadcast the current game state to all clients."""
        if not self.arena or not self.clients:
            return

        # Collect all network objects
        # Build character states with input ID tracking
        character_states = []
        for char in self.arena.characters:
            char_state = char.__getstate__()
            # Add last input ID for the player controlling this character
            controlling_player = None
            for player_id, char_id in self.player_id_to_character.items():
                if char_id == char.id:
                    controlling_player = player_id
                    break
            if controlling_player:
                char_state['last_input_id'] = self.last_input_ids.get(controlling_player, 0)
            else:
                char_state['last_input_id'] = 0
            character_states.append(char_state)

        game_state = {
            'type': 'game_state',
            'timestamp': time.time(),
            'characters': character_states,
            'projectiles': [proj.__getstate__() for proj in self.arena.projectiles],
            'weapons': [weapon.__getstate__() for weapon in self.arena.weapon_pickups],
            'platforms': [platform.__getstate__() for platform in self.arena.platforms],
            'game_over': self.arena.game_over,
            'winner': self.arena.winner
        }



        # Serialize once
        data = pickle.dumps(game_state)
        length_bytes = len(data).to_bytes(4, byteorder='big')

        # Send to all clients
        disconnected_clients = []
        for player_id, client_socket in self.clients.items():
            try:
                client_socket.send(length_bytes + data)
            except Exception as e:
                print(f"Failed to send to {player_id}: {e}")
                disconnected_clients.append(player_id)

        # Clean up disconnected clients
        for player_id in disconnected_clients:
            self._handle_client_disconnect(player_id)


def main():
    """Main server entry point."""
    # Clean up old log files before starting
    cleanup_old_logs()

    import argparse

    parser = argparse.ArgumentParser(description='GenGame Server')
    parser.add_argument('--host', default='127.0.0.1', help='Server host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5555, help='Server port (default: 5555)')

    args = parser.parse_args()

    server = GameServer(args.host, args.port)

    try:
        server.start()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.stop()


if __name__ == "__main__":
    main()
