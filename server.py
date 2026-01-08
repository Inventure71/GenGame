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
from coding.non_callable_tools.version_control import VersionControl
from coding.tools.conflict_resolution import get_all_conflicts
from testing import auto_fix_conflicts




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

        # Pending connections (sockets waiting for player_name)
        self.pending_clients: Dict[socket.socket, Tuple[str, int]] = {}  # socket -> (ip, port)

        # Game state
        self.arena = None
        self.tick_rate = 60  # 60 FPS simulation
        self.tick_interval = 1.0 / self.tick_rate
        self.last_tick_time = 0.0
        self.game_start_time = 0.0

        # File synchronization
        self.game_files = {}  # filename -> content
        self._load_game_files()

        # Patch synchronization for game start
        self.clients_patch_received: Set[str] = set()  # Track which clients have received patches
        self.clients_patch_ready: Set[str] = set()  # Track which clients have applied patches successfully
        self.clients_patch_failed: Dict[str, str] = {}  # Track which clients failed: player_id -> error_message
        self.waiting_for_patch_sync = False  # Flag to indicate we're waiting for patch sync
        self.waiting_for_patch_received = False  # Flag to indicate we're waiting for patch reception
        
        # Server-side patch management
        self.server_patches_dir = "__server_patches"
        os.makedirs(self.server_patches_dir, exist_ok=True)
        self.client_patches: Dict[str, List[Dict]] = {}  # player_id -> list of patch info
        self.client_patch_files: Dict[str, Dict] = {}  # (player_id, patch_name) -> {'chunks': {}, 'total': N}
        self.clients_ready_status: Set[str] = set()  # Track which clients marked as ready

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

        # Arena will be created dynamically when first client requests file sync
        # This allows us to create the arena with the correct number of connected players
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

        # Add to pending clients - wait for player_name message
        self.pending_clients[client_socket] = address
        client_socket.setblocking(False)

        print(f"Waiting for player_name from {address}")

    def _recreate_arena_with_players(self):
        """Recreate the arena with the currently connected players."""
        # Get list of connected player names (these are already the custom names)
        connected_player_names = list(self.clients.keys())
        print(f"Recreating arena with players: {connected_player_names}")

        # Recreate arena with actual player names
        self.arena = setup_battle_arena(width=1400, height=900, headless=True, player_names=connected_player_names)

        # Set character IDs to match player names
        for i, character in enumerate(self.arena.characters):
            if i < len(connected_player_names):
                player_name = connected_player_names[i]
                character.id = player_name

    def _initiate_game_start_with_patch_sync(self):
        """Generate merge patch and send to all clients, then wait for them to apply."""
        print("Initiating game start with patch synchronization...")
        
        # Generate merge_patch.json from all patches in __patches directory
        merge_patch_path = self._generate_merge_patch()
        
        if not merge_patch_path or not os.path.exists(merge_patch_path):
            print("No patches to merge or generation failed, starting game directly")
            self._notify_all_clients_game_start()
            return
        
        # Send the merge patch to all clients
        print(f"Sending merge patch to all clients: {merge_patch_path}")
        self.waiting_for_patch_received = True
        self.clients_patch_received.clear()
        self.clients_patch_ready.clear()
        self.clients_patch_failed.clear()

        for player_id in self.clients.keys():
            self._send_patch_file(player_id, merge_patch_path)
    
    def _generate_merge_patch(self) -> Optional[str]:
        """Generate a single merge_patch.json from all patches in __patches directory.
        
        For now: Returns the first existing patch file found.
        
        TODO: Implement proper 3-way merging for multiple patches using:
              from coding.non_callable_tools.version_control import VersionControl
              vc = VersionControl()
              success, output = vc.merge_patches(
                  base_backup_path="__game_backups",
                  patch_a_path=patch_files[0],
                  patch_b_path=patch_files[1],
                  output_path=os.path.join(patches_dir, "merge_patch.json")
              )
              For >2 patches, merge iteratively: merge(merge(A,B), C), etc.
        """
        patches_dir = os.path.join(os.path.dirname(__file__), "__patches")
        
        if not os.path.exists(patches_dir):
            print("No __patches directory found")
            return None
        
        # Find all .json patch files (excluding merge_patch.json to avoid circular logic)
        patch_files = [f for f in glob.glob(os.path.join(patches_dir, "*.json")) 
                       if not f.endswith("merge_patch.json")]
        
        if not patch_files:
            print("No patch files found in __patches directory")
            return None
        
        # FOR NOW: Just use the first patch file as-is
        if len(patch_files) == 1:
            print(f"Using single patch file: {os.path.basename(patch_files[0])}")
            return patch_files[0]
        else:
            # Multiple patches exist - for now just use the first one
            print(f"⚠️  Found {len(patch_files)} patches:")
            for pf in patch_files:
                print(f"    - {os.path.basename(pf)}")
            print(f"⚠️  Using only first patch: {os.path.basename(patch_files[0])}")
            print(f"⚠️  TODO: Implement proper 3-way merge using VersionControl.merge_patches()")
            return patch_files[0]
    
    def _send_patch_file(self, player_id: str, patch_file_path: str):
        """Send a patch file to a specific client."""
        try:
            client_socket = self.clients[player_id]
            
            # Read the patch file
            with open(patch_file_path, 'rb') as f:
                patch_content = f.read()
            
            # Send patch data message
            message = {
                'type': 'patch_file',
                'filename': 'merge_patch.json',
                'content': patch_content,
                'size': len(patch_content)
            }
            
            data = pickle.dumps(message)
            length_bytes = len(data).to_bytes(4, byteorder='big')
            client_socket.send(length_bytes + data)
            
            print(f"Sent merge patch to {player_id} ({len(patch_content)} bytes)")
        except Exception as e:
            print(f"Failed to send patch to {player_id}: {e}")

    def _notify_all_clients_game_start(self):
        """Notify all connected clients to start the game."""
        print("Notifying all clients to start game...")

        message = {
            'type': 'game_start'
        }
        data = pickle.dumps(message)
        length_bytes = len(data).to_bytes(4, byteorder='big')

        for player_id, client_socket in self.clients.items():
            try:
                client_socket.send(length_bytes + data)
                print(f"Sent game_start to {player_id}")
            except Exception as e:
                print(f"Failed to send game_start to {player_id}: {e}")
    
    def _notify_patch_sync_failed(self):
        """Notify all clients that patch synchronization failed and game cannot start."""
        print("Notifying all clients that patch sync failed...")
        
        # Build failure details
        failure_details = []
        for failed_player, error in self.clients_patch_failed.items():
            failure_details.append(f"{failed_player}: {error}")
        
        message = {
            'type': 'patch_sync_failed',
            'reason': 'One or more clients failed to apply the merge patch',
            'failed_clients': list(self.clients_patch_failed.keys()),
            'details': failure_details
        }
        data = pickle.dumps(message)
        length_bytes = len(data).to_bytes(4, byteorder='big')
        
        for player_id, client_socket in self.clients.items():
            try:
                client_socket.send(length_bytes + data)
                print(f"Sent patch_sync_failed notification to {player_id}")
            except Exception as e:
                print(f"Failed to send patch_sync_failed to {player_id}: {e}")

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
        # Check both regular clients and pending clients
        sockets_to_check = list(self.clients.values()) + list(self.pending_clients.keys())

        if not sockets_to_check:
            return

        try:
            readable, _, _ = select.select(sockets_to_check, [], [], 0.01)

            for client_socket in readable:
                try:
                    # Find player_id for this socket (check both regular and pending clients)
                    player_id = None
                    is_pending = False

                    # Check regular clients first
                    for pid, sock in self.clients.items():
                        if sock == client_socket:
                            player_id = pid
                            break

                    # If not found, check pending clients
                    if not player_id:
                        if client_socket in self.pending_clients:
                            is_pending = True
                            player_id = "pending"  # Temporary identifier for pending clients
                        else:
                            continue

                    # Receive message
                    length_bytes = client_socket.recv(4)
                    if not length_bytes:
                        # Client disconnected
                        if is_pending:
                            # Pending client disconnected
                            if client_socket in self.pending_clients:
                                address = self.pending_clients[client_socket]
                                del self.pending_clients[client_socket]
                                print(f"Pending client from {address} disconnected before sending player_name")
                        else:
                            # Regular client disconnected
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
                        self._process_client_message(player_id, message, client_socket)

                except Exception as e:
                    # Client likely disconnected
                    if is_pending:
                        # Pending client disconnected
                        if client_socket in self.pending_clients:
                            address = self.pending_clients[client_socket]
                            del self.pending_clients[client_socket]
                            print(f"Pending client from {address} disconnected: {e}")
                    else:
                        # Regular client disconnected
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
            # Remove from active character mapping
            if player_id in self.player_id_to_character:
                del self.player_id_to_character[player_id]
            print(f"Client {player_id} disconnected")

    def _process_client_message(self, player_id: str, message: dict, client_socket: socket.socket = None):
        """Process a message from a client."""
        msg_type = message.get('type', 'input')

        if msg_type == 'input':
            # Add to input queue
            self.input_queues[player_id].append(message)
        elif msg_type == 'request_file_sync':
            # Client requested file synchronization
            # If this is the first file sync request, recreate the arena with current players
            if not hasattr(self, '_arena_initialized'):
                self._recreate_arena_with_players()
                self._arena_initialized = True

            self._send_file_sync(player_id)
        elif msg_type == 'request_start_game':
            # Client requested to start the game - send merge patch to all clients
            print(f"Player {player_id} requested to start game")
            self._initiate_game_start_with_patch_sync()
        elif msg_type == 'patch_received':
            # Client acknowledged that they've received the patch
            print(f"📦 {player_id} received the merge patch")

            if self.waiting_for_patch_received:
                self.clients_patch_received.add(player_id)

                # Check if all clients have received the patch
                all_clients = set(self.clients.keys())
                if self.clients_patch_received == all_clients:
                    print("✅ All clients have received the patch - now waiting for application")
                    self.waiting_for_patch_received = False
                    self.waiting_for_patch_sync = True
        elif msg_type == 'patch_applied':
            # Client acknowledged that they've applied the patch
            patch_success = message.get('success', True)
            error_message = message.get('error', None)
            
            if patch_success:
                print(f"✅ {player_id} successfully applied the merge patch")
                self.clients_patch_ready.add(player_id)
            else:
                print(f"❌ {player_id} FAILED to apply the merge patch: {error_message}")
                self.clients_patch_failed[player_id] = error_message
            
            # Check if all clients have applied the patch (success or failure)
            all_clients = set(self.clients.keys())
            responded_clients = self.clients_patch_ready | set(self.clients_patch_failed.keys())

            if self.waiting_for_patch_sync and responded_clients == all_clients:
                print(f"\nPatch sync complete: {len(self.clients_patch_ready)} succeeded, {len(self.clients_patch_failed)} failed")
                
                # Only start game if ALL clients succeeded
                if len(self.clients_patch_failed) == 0:
                    print("✅ All clients ready - starting game!")
                    self.waiting_for_patch_received = False
                    self.waiting_for_patch_sync = False
                    self.clients_patch_received.clear()
                    self.clients_patch_ready.clear()
                    self._notify_all_clients_game_start()
                else:
                    print("❌ Cannot start game - patch application failed on some clients:")
                    for failed_player, error in self.clients_patch_failed.items():
                        print(f"  - {failed_player}: {error}")
                    
                    # Notify all clients that game start was aborted
                    self._notify_patch_sync_failed()
                    
                    # Reset state
                    self.waiting_for_patch_received = False
                    self.waiting_for_patch_sync = False
                    self.clients_patch_received.clear()
                    self.clients_patch_ready.clear()
                    self.clients_patch_failed.clear()
        elif msg_type == 'file_sync_ack':
            # Client acknowledged file sync
            print(f"{player_id} acknowledged file sync")
        elif msg_type == 'player_name':
            # Client sent their requested player name
            requested_name = message.get('player_name')
            if requested_name:
                # Check if this is a pending client
                if player_id == "pending" and client_socket in self.pending_clients:
                    # Promote pending client to regular client using their custom name as player_id
                    client_address = self.pending_clients[client_socket]
                    actual_player_id = requested_name

                    # Check if this player name is already taken
                    if actual_player_id in self.clients:
                        print(f"Player name '{requested_name}' already taken, rejecting")
                        # Send rejection message
                        response = {
                            'type': 'name_rejected',
                            'reason': 'Name already taken'
                        }
                        data = pickle.dumps(response)
                        length_bytes = len(data).to_bytes(4, byteorder='big')
                        try:
                            client_socket.send(length_bytes + data)
                        except:
                            pass
                        return

                    # Accept the client
                    self.clients[actual_player_id] = client_socket
                    self.client_addresses[actual_player_id] = client_address
                    self.input_queues[actual_player_id] = []
                    del self.pending_clients[client_socket]
                    player_id = actual_player_id
                    print(f"Player '{requested_name}' registered with custom ID")

                self.player_name_to_id[requested_name] = player_id

                # Use the custom name directly as character ID
                character_id = requested_name
                self.player_id_to_character[player_id] = character_id

                print(f"Player '{requested_name}' connected as {character_id}")

                # Send back the assigned character info
                response = {
                    'type': 'character_assignment',
                    'requested_name': requested_name,
                    'assigned_character': requested_name  # Use the requested name for display
                }
                data = pickle.dumps(response)
                length_bytes = len(data).to_bytes(4, byteorder='big')
                try:
                    self.clients[player_id].send(length_bytes + data)
                except Exception as e:
                    print(f"Failed to send character assignment: {e}")
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
        elif msg_type == 'patches_selection':
            # Client sent their patch selection
            patches = message.get('patches', [])
            self.client_patches[player_id] = patches
            print(f"{player_id} selected {len(patches)} patch(es)")
        elif msg_type == 'patch_chunk':
            # Client sending a patch file chunk
            self._handle_patch_chunk(player_id, message)
        elif msg_type == 'patches_ready':
            # Client marked patches as ready
            self.clients_ready_status.add(player_id)
            print(f"{player_id} marked as ready ({len(self.clients_ready_status)}/{len(self.clients)})")
            
            # Check if all clients are ready
            if self.clients_ready_status == set(self.clients.keys()):
                print("All clients ready - initiating patch merge and distribution")
                self._merge_and_distribute_patches()

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
    
    def _handle_patch_chunk(self, player_id: str, message: dict):
        """Handle incoming patch file chunk from client."""
        patch_name = message.get('patch_name')
        chunk_num = message.get('chunk_num')
        total_chunks = message.get('total_chunks')
        chunk_data = message.get('data')
        
        if not all([patch_name, isinstance(chunk_num, int), isinstance(total_chunks, int), chunk_data]):
            print(f"Invalid patch chunk from {player_id}")
            return
        
        # Create tracking key
        key = f"{player_id}:{patch_name}"
        
        if key not in self.client_patch_files:
            self.client_patch_files[key] = {
                'chunks': {},
                'total': total_chunks,
                'received': 0
            }
        
        transfer = self.client_patch_files[key]
        
        # Store chunk if not already received
        if chunk_num not in transfer['chunks']:
            transfer['chunks'][chunk_num] = chunk_data
            transfer['received'] += 1
        
        # Check if complete
        if transfer['received'] == total_chunks:
            self._assemble_patch_file(player_id, patch_name)
    
    def _assemble_patch_file(self, player_id: str, patch_name: str):
        """Assemble complete patch file from chunks."""
        key = f"{player_id}:{patch_name}"
        transfer = self.client_patch_files[key]
        
        try:
            # Create player's patch directory
            player_patch_dir = os.path.join(self.server_patches_dir, player_id)
            os.makedirs(player_patch_dir, exist_ok=True)
            
            # Write file
            patch_path = os.path.join(player_patch_dir, f"{patch_name}.json")
            with open(patch_path, 'wb') as f:
                for chunk_num in range(transfer['total']):
                    if chunk_num in transfer['chunks']:
                        f.write(transfer['chunks'][chunk_num])
                    else:
                        raise ValueError(f"Missing chunk {chunk_num}")
            
            print(f"✅ Received complete patch from {player_id}: {patch_name}")
            
            # Clean up transfer state
            del self.client_patch_files[key]
            
        except Exception as e:
            print(f"Failed to assemble patch from {player_id}: {e}")

    def _merge_and_distribute_patches(self):
        """
        Merge all patches from all clients with retry logic.
        Uses auto_fix_conflicts if there are merge conflicts.
        """
        print("\n" + "="*60)
        print("STARTING PATCH MERGE PROCESS")
        print("="*60)
        
        # Step 1: Validate base backup compatibility
        all_patches_info = list(self.client_patches.values())
        compatible, error = self._validate_base_backup_compatibility(all_patches_info)
        
        if not compatible:
            print(f"❌ Base backup validation failed: {error}")
            self._notify_patch_merge_failed(f"Incompatible patches: {error}")
            return
        
        print("✅ Base backup validation passed")
        
        # Step 2: Collect all patch file paths
        all_patch_paths = []
        for player_id, patches_info in self.client_patches.items():
            for patch_info in patches_info:
                patch_name = patch_info['name']
                patch_path = os.path.join(self.server_patches_dir, player_id, f"{patch_name}.json")
                if os.path.exists(patch_path):
                    all_patch_paths.append(patch_path)
        
        print(f"Found {len(all_patch_paths)} patch files to merge")
        
        if len(all_patch_paths) == 0:
            print("No patches to merge, starting game directly")
            self._notify_all_clients_game_start()
            return
        
        # Step 3: Merge patches with retry logic
        output_path = os.path.join(self.server_patches_dir, "merged_patch.json")
        success = False
        
        for attempt in range(3):
            print(f"\n--- Merge Attempt {attempt + 1}/3 ---")
            
            # Merge all patches iteratively
            success, result = self._merge_patches_iteratively(all_patch_paths, output_path)
            
            if success:
                print(f"✅ Merge successful on attempt {attempt + 1}")
                break
            else:
                print(f"⚠️  Merge had conflicts: {result}")
                
                # Try to auto-fix conflicts
                print("Running auto_fix_conflicts...")
                try:
                    base_backup_name = all_patches_info[0][0].get('base_backup', 'Unknown')
                    auto_fix_conflicts(output_path, patch_paths=all_patch_paths, base_backup=base_backup_name)
                    
                    # Check if conflicts remain
                    remaining_conflicts = get_all_conflicts(output_path)
                    if len(remaining_conflicts) == 0:
                        print("✅ Auto-fix resolved all conflicts!")
                        success = True
                        break
                    else:
                        print(f"⚠️  {len(remaining_conflicts)} conflicts remain after auto-fix")
                except Exception as e:
                    print(f"❌ Auto-fix failed: {e}")
        
        # Step 4: Check final result
        if not success:
            print("\n❌ MERGE FAILED AFTER 3 ATTEMPTS")
            self._notify_patch_merge_failed("Patches are incompatible - could not resolve conflicts after 3 attempts")
            return
        
        print("\n✅ MERGE SUCCESSFUL - Distributing to clients")
        
        # Step 5: Send merged patch to all clients
        self._initiate_game_start_with_patch_sync(output_path)
    
    def _validate_base_backup_compatibility(self, all_patches_info: List[List[Dict]]) -> tuple:
        """Validate that all patches use the same base backup."""
        all_base_backups = set()
        
        for client_patches in all_patches_info:
            for patch_info in client_patches:
                all_base_backups.add(patch_info.get('base_backup', 'Unknown'))
        
        if len(all_base_backups) == 0:
            return True, None
        
        if len(all_base_backups) > 1:
            return False, f"Different base backups: {', '.join(all_base_backups)}"
        
        return True, None
    
    def _merge_patches_iteratively(self, patch_paths: List[str], output_path: str) -> tuple:
        """
        Merge multiple patches iteratively: merge(merge(A, B), C), etc.
        Returns (success, result_message)
        """
        if len(patch_paths) == 0:
            return False, "No patches to merge"
        
        if len(patch_paths) == 1:
            # Only one patch - just copy it
            import shutil
            shutil.copy(patch_paths[0], output_path)
            return True, "Single patch copied"
        
        # Get base backup name from first patch
        import json
        with open(patch_paths[0], 'r') as f:
            data = json.load(f)
            base_backup_name = data.get('name_of_backup', 'Unknown')
        
        # Create version control instance
        vc = VersionControl()
        
        # Start with first two patches
        current_output = output_path
        success, result = vc.merge_patches(
            base_backup_path="__game_backups",
            patch_a_path=patch_paths[0],
            patch_b_path=patch_paths[1],
            output_path=current_output
        )
        
        if not success and "conflicts" not in result.lower():
            return False, result
        
        # Merge remaining patches one by one
        for i in range(2, len(patch_paths)):
            temp_output = output_path + f".temp{i}"
            
            # Merge current result with next patch
            success, result = vc.merge_patches(
                base_backup_path="__game_backups",
                patch_a_path=current_output,
                patch_b_path=patch_paths[i],
                output_path=temp_output
            )
            
            # Move temp to current
            import shutil
            shutil.move(temp_output, current_output)
            
            if not success and "conflicts" not in result.lower():
                return False, result
        
        # Check for conflicts in final result
        conflicts = get_all_conflicts(current_output)
        if len(conflicts) > 0:
            return False, f"Merge completed with {len(conflicts)} file(s) having conflicts"
        
        return True, "Merge successful"
    
    def _initiate_game_start_with_patch_sync(self, patch_path: str):
        """Send merged patch to all clients for application."""
        print("Sending merged patch to all clients...")
        
        self.waiting_for_patch_received = True
        self.clients_patch_received.clear()
        self.clients_patch_ready.clear()
        self.clients_patch_failed.clear()
        
        for player_id in self.clients.keys():
            self._send_patch_file(player_id, patch_path)
    
    def _notify_patch_merge_failed(self, reason: str):
        """Notify all clients that patch merge failed."""
        print(f"Notifying clients: {reason}")
        
        message = {
            'type': 'patch_merge_failed',
            'reason': reason
        }
        data = pickle.dumps(message)
        length_bytes = len(data).to_bytes(4, byteorder='big')
        
        for player_id, client_socket in self.clients.items():
            try:
                client_socket.send(length_bytes + data)
            except Exception as e:
                print(f"Failed to notify {player_id}: {e}")
        
        # Reset state
        self.clients_ready_status.clear()
        self.client_patches.clear()
    
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
            'ammo_pickups': [ammo.__getstate__() for ammo in self.arena.ammo_pickups],
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
