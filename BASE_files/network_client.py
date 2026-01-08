#!/usr/bin/env python3
"""
GenGame Network Client - Handles connection to server and entity synchronization
"""

import socket
import threading
import time
import pickle
import os
import sys
import importlib
from typing import Dict, List, Optional, Callable, Any
from collections import deque
import select

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from BASE_files.BASE_network import NetworkObject


class NetworkClient:
    """
    Client-side network manager that handles server communication and entity synchronization.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 5555):
        self.host = host
        self.port = port
        self.connected = False
        self.socket = None
        self.player_id = None

        # Network state
        self.receive_thread = None
        self.running = False

        # Message queues
        self.incoming_queue = deque()
        self.outgoing_queue = deque()

        # Callbacks
        self.on_file_sync_received = None
        self.on_game_state_received = None
        self.on_character_assigned = None
        self.on_disconnected = None
        self.on_file_received = None
        self.on_file_transfer_progress = None
        self.on_name_rejected = None
        self.on_patch_received = None  # New callback for when patch is received
        self.on_patch_sync_failed = None  # New callback for when patch sync fails
        self.on_patch_merge_failed = None  # New callback for when server merge fails
        self.on_game_start = None

        # Lag compensation
        self.last_server_time = 0.0
        self.latency = 0.0

        # File transfer state
        self.file_transfers = {}  # file_path -> {'chunks': {}, 'total_chunks': 0, 'received_chunks': 0}

    def connect(self, player_id: str) -> bool:
        """Connect to the server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.socket.setblocking(False)
            self.player_id = player_id
            self.connected = True
            self.running = True

            # Start receive thread
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()

            print(f"Connected to server at {self.host}:{self.port} as {player_id}")

            # Send player name to server
            self._send_player_name(player_id)

            return True

        except Exception as e:
            print(f"Failed to connect: {e}")
            return False

    def disconnect(self):
        """Disconnect from the server."""
        self.running = False
        self.connected = False

        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

        if self.on_disconnected:
            self.on_disconnected()

        print("Disconnected from server")

    def send_input(self, input_data: dict, entity_manager=None):
        """Send player input to the server."""
        if not self.connected:
            return

        message = {
            'type': 'input',
            'player_id': self.player_id,
            **input_data
        }

        # Add to prediction system if entity manager is provided
        if entity_manager and hasattr(entity_manager, 'prediction'):
            input_id = entity_manager.prediction.add_input(input_data)
            message['input_id'] = input_id

        self.outgoing_queue.append(message)

    def _send_player_name(self, player_name: str):
        """Send the requested player name to the server."""
        message = {
            'type': 'player_name',
            'player_name': player_name
        }
        self.outgoing_queue.append(message)

    def request_file_sync(self):
        """Request file synchronization from server."""
        if not self.connected:
            return

        message = {
            'type': 'request_file_sync'
        }
        self.outgoing_queue.append(message)

    def request_start_game(self):
        """Request to start the game (host only)."""
        if not self.connected:
            return

        message = {
            'type': 'request_start_game'
        }
        self.outgoing_queue.append(message)
    
    def send_patches_selection(self, patches_info: list):
        """Send selected patches info and files to server."""
        if not self.connected:
            return
        
        # First, send the selection metadata
        message = {
            'type': 'patches_selection',
            'player_id': self.player_id,
            'patches': patches_info
        }
        self.outgoing_queue.append(message)
        print(f"Sent patches selection: {[p['name'] for p in patches_info]}")
        
        # Then send each patch file
        for patch_info in patches_info:
            file_path = patch_info['file_path']
            if os.path.exists(file_path):
                self._send_patch_file(file_path, patch_info['name'])
        
        # Mark as ready ONCE after all files sent
        self.mark_patches_ready()
    
    def _send_patch_file(self, file_path: str, patch_name: str):
        """Send a patch file to server in chunks."""
        try:
            file_size = os.path.getsize(file_path)
            chunk_size = 64 * 1024  # 64KB chunks
            total_chunks = (file_size + chunk_size - 1) // chunk_size
            
            with open(file_path, 'rb') as f:
                for chunk_num in range(total_chunks):
                    chunk_data = f.read(chunk_size)
                    
                    message = {
                        'type': 'patch_chunk',
                        'patch_name': patch_name,
                        'chunk_num': chunk_num,
                        'total_chunks': total_chunks,
                        'data': chunk_data,
                        'player_id': self.player_id
                    }
                    
                    self.outgoing_queue.append(message)
            
            print(f"Sent patch file: {patch_name} ({total_chunks} chunks)")
            
        except Exception as e:
            print(f"Failed to send patch file {file_path}: {e}")
    
    def mark_patches_ready(self):
        """Mark patches as ready (all files uploaded)."""
        message = {
            'type': 'patches_ready',
            'player_id': self.player_id
        }
        self.outgoing_queue.append(message)
        print("Marked patches as ready")

    def acknowledge_file_sync(self):
        """Send acknowledgment that file sync was received."""
        if not self.connected:
            return

        message = {
            'type': 'file_sync_ack',
            'player_id': self.player_id
        }

        self.outgoing_queue.append(message)

    def request_file(self, file_path: str) -> bool:
        """
        Request a file from the server.

        Args:
            file_path: Path of the file to request from server

        Returns:
            bool: True if request was sent successfully
        """
        if not self.connected:
            return False

        message = {
            'type': 'file_request',
            'file_path': file_path,
            'player_id': self.player_id
        }

        self.outgoing_queue.append(message)
        return True

    def send_file(self, file_path: str, target_path: str = None) -> bool:
        """
        Send a file to the server.

        Args:
            file_path: Local path of the file to send
            target_path: Path where the file should be stored on server (optional)

        Returns:
            bool: True if file transfer was initiated successfully
        """
        if not self.connected:
            return False

        try:
            # Check if file exists and get its size
            if not os.path.exists(file_path):
                print(f"File not found: {file_path}")
                return False

            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            target_path = target_path or file_name

            # Read file in chunks to avoid memory issues
            chunk_size = 64 * 1024  # 64KB chunks
            total_chunks = (file_size + chunk_size - 1) // chunk_size

            with open(file_path, 'rb') as f:
                for chunk_num in range(total_chunks):
                    chunk_data = f.read(chunk_size)

                    message = {
                        'type': 'file_chunk',
                        'file_path': target_path,
                        'chunk_num': chunk_num,
                        'total_chunks': total_chunks,
                        'data': chunk_data,
                        'player_id': self.player_id
                    }

                    self.outgoing_queue.append(message)

                    # Call progress callback if available
                    if self.on_file_transfer_progress:
                        progress = (chunk_num + 1) / total_chunks
                        self.on_file_transfer_progress(target_path, progress, 'sending')

            return True

        except Exception as e:
            print(f"Failed to send file {file_path}: {e}")
            return False

    def update(self):
        """Update network client (call this regularly)."""
        if not self.connected:
            return

        # Send outgoing messages
        self._send_outgoing_messages()

        # Process incoming messages
        self._process_incoming_messages()

    def _receive_loop(self):
        """Background thread for receiving messages."""
        while self.running and self.connected:
            try:
                # Check if socket is readable
                readable, _, _ = select.select([self.socket], [], [], 0.01)

                if readable:
                    # Receive message length
                    length_bytes = self.socket.recv(4)
                    if not length_bytes:
                        # Server disconnected
                        self.disconnect()
                        break

                    message_length = int.from_bytes(length_bytes, byteorder='big')

                    # Receive the actual message
                    data = b''
                    while len(data) < message_length:
                        chunk = self.socket.recv(message_length - len(data))
                        if not chunk:
                            break
                        data += chunk

                    if len(data) == message_length:
                        message = pickle.loads(data)
                        self.incoming_queue.append(message)

            except Exception as e:
                if self.running:  # Only print error if we're supposed to be running
                    print(f"Receive error: {e}")
                    self.disconnect()
                break

    def _send_outgoing_messages(self):
        """Send queued outgoing messages."""
        while self.outgoing_queue:
            try:
                message = self.outgoing_queue.popleft()
                data = pickle.dumps(message)
                length_bytes = len(data).to_bytes(4, byteorder='big')
                self.socket.send(length_bytes + data)
            except Exception as e:
                print(f"Send error: {e}")
                self.disconnect()
                break

    def _process_incoming_messages(self):
        """Process received messages."""
        while self.incoming_queue:
            message = self.incoming_queue.popleft()
            self._handle_message(message)

    def _handle_message(self, message: dict):
        """Handle a received message."""
        msg_type = message.get('type')

        if msg_type == 'file_sync':
            if self.on_file_sync_received:
                self.on_file_sync_received(message['files'])
        elif msg_type == 'name_rejected':
            reason = message.get('reason', 'Unknown reason')
            print(f"Player name rejected: {reason}")
            if self.on_name_rejected:
                self.on_name_rejected(reason)
            else:
                self.disconnect()
        elif msg_type == 'game_start':
            print("Received game_start notification - starting game!")
            if self.on_game_start:
                self.on_game_start()
        elif msg_type == 'game_state':
            if self.on_game_state_received:
                self.on_game_state_received(message)
        elif msg_type == 'character_assignment':
            if self.on_character_assigned:
                self.on_character_assigned(message)
        elif msg_type == 'file_chunk':
            self._handle_file_chunk(message)
        elif msg_type == 'file_complete':
            if self.on_file_received:
                self.on_file_received(message['file_path'], message.get('success', True))
        elif msg_type == 'patch_file':
            self._handle_patch_file(message)
        elif msg_type == 'patch_sync_failed':
            reason = message.get('reason', 'Unknown reason')
            failed_clients = message.get('failed_clients', [])
            details = message.get('details', [])
            print(f"❌ Patch sync failed: {reason}")
            print(f"Failed clients: {', '.join(failed_clients)}")
            for detail in details:
                print(f"  - {detail}")
            if self.on_patch_sync_failed:
                self.on_patch_sync_failed(reason, failed_clients, details)
        elif msg_type == 'patch_merge_failed':
            reason = message.get('reason', 'Unknown reason')
            print(f"❌ Patch merge failed on server: {reason}")
            if self.on_patch_merge_failed:
                self.on_patch_merge_failed(reason)

    def _handle_file_chunk(self, message: dict):
        """Handle incoming file chunk."""
        file_path = message['file_path']
        chunk_num = message['chunk_num']
        total_chunks = message['total_chunks']
        chunk_data = message['data']

        # Initialize file transfer if this is the first chunk
        if file_path not in self.file_transfers:
            self.file_transfers[file_path] = {
                'chunks': {},
                'total_chunks': total_chunks,
                'received_chunks': 0,
                'start_time': time.time()
            }

        transfer = self.file_transfers[file_path]

        # Store the chunk
        if chunk_num not in transfer['chunks']:
            transfer['chunks'][chunk_num] = chunk_data
            transfer['received_chunks'] += 1

            # Call progress callback if available
            if self.on_file_transfer_progress:
                progress = transfer['received_chunks'] / total_chunks
                self.on_file_transfer_progress(file_path, progress, 'receiving')

        # Check if file is complete
        if transfer['received_chunks'] == total_chunks:
            self._assemble_file(file_path)

    def _assemble_file(self, file_path: str):
        """Assemble received chunks into a complete file."""
        transfer = self.file_transfers[file_path]

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Write file by combining chunks in order
            with open(file_path, 'wb') as f:
                for chunk_num in range(transfer['total_chunks']):
                    if chunk_num in transfer['chunks']:
                        f.write(transfer['chunks'][chunk_num])
                    else:
                        raise ValueError(f"Missing chunk {chunk_num} for file {file_path}")

            # Send acknowledgment to server
            message = {
                'type': 'file_ack',
                'file_path': file_path,
                'player_id': self.player_id,
                'success': True
            }
            self.outgoing_queue.append(message)

            # Call completion callback
            if self.on_file_received:
                self.on_file_received(file_path, True)

            print(f"File received successfully: {file_path}")

        except Exception as e:
            print(f"Failed to assemble file {file_path}: {e}")

            # Send failure acknowledgment
            message = {
                'type': 'file_ack',
                'file_path': file_path,
                'player_id': self.player_id,
                'success': False,
                'error': str(e)
            }
            self.outgoing_queue.append(message)

            # Call completion callback with failure
            if self.on_file_received:
                self.on_file_received(file_path, False)

        finally:
            # Clean up transfer state
            if file_path in self.file_transfers:
                del self.file_transfers[file_path]
    
    def _handle_patch_file(self, message: dict):
        """Handle incoming patch file from server."""
        filename = message.get('filename', 'merge_patch.json')
        content = message.get('content', b'')

        print(f"Received patch file: {filename} ({len(content)} bytes)")

        # Save patch to local directory
        patch_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "__patches")
        os.makedirs(patch_dir, exist_ok=True)

        patch_path = os.path.join(patch_dir, filename)

        try:
            with open(patch_path, 'wb') as f:
                f.write(content)
            print(f"Saved patch to: {patch_path}")

            # Send acknowledgment that patch was received
            self._send_patch_received()

            # Now apply the patch
            if self.on_patch_received:
                self.on_patch_received(patch_path)
        except Exception as e:
            print(f"Error saving patch file: {e}")
            # Send failure acknowledgment
            self.send_patch_applied(success=False, error_message=f"Failed to receive patch file: {str(e)}")

    def _send_patch_received(self):
        """Send acknowledgment that patch file was received."""
        message = {'type': 'patch_received', 'player_id': self.player_id}
        self.outgoing_queue.append(message)
        print("Sent patch_received acknowledgment to server")
    
    def send_patch_applied(self, success: bool = True, error_message: str = None):
        """Send acknowledgment to server that patch has been applied.
        
        Args:
            success: Whether patch was applied successfully
            error_message: Optional error message if success is False
        """
        message = {
            'type': 'patch_applied',
            'player_id': self.player_id,
            'success': success,
            'error': error_message
        }
        self.outgoing_queue.append(message)
        status = "successfully" if success else "with errors"
        print(f"Sent patch_applied acknowledgment to server: {status}")
        if error_message:
            print(f"  Error: {error_message}")


class ClientPrediction:
    """
    Minimal prediction system for input ID tracking only.
    """

    def __init__(self):
        self.pending_inputs = []  # List of (input_id, input_data, timestamp)
        self.input_id_counter = 0

    def add_input(self, input_data: dict) -> int:
        """Add an input to the queue and return its ID."""
        self.input_id_counter += 1
        input_id = self.input_id_counter

        self.pending_inputs.append({
            'id': input_id,
            'data': input_data,
            'timestamp': time.time()
        })

        return input_id

    def reconcile_with_server(self, server_entity_data: dict):
        """Clean up acknowledged inputs to prevent memory buildup."""
        last_acknowledged_id = server_entity_data.get('last_input_id', 0)
        self.pending_inputs = [
            inp for inp in self.pending_inputs
            if inp['id'] > last_acknowledged_id
        ]

    def get_predicted_state(self) -> dict:
        """Get current state (minimal implementation)."""
        return {'last_input_id': 0}


class EntityManager:
    """
    Manages the lifecycle of ghost objects (network-synchronized entities).
    """

    def __init__(self):
        self.entities: Dict[str, Any] = {}  # network_id -> entity instance
        self.platforms: Dict[str, Any] = {}  # network_id -> platform instance
        self.local_player_id = None

        # Interpolation buffers for smooth movement
        self.interpolation_buffers: Dict[str, deque] = {}
        self.max_buffer_size = 3  # Keep last 3 snapshots for interpolation

        # Client-side prediction
        self.prediction = ClientPrediction()

    def set_local_player(self, player_id: str):
        """Set which player entity is controlled locally."""
        self.local_player_id = player_id

    def update_from_server(self, game_state: dict):
        """
        Update entities from server game state.
        Creates new entities, updates existing ones, and removes missing ones.
        """
        server_entities = {
            'characters': game_state.get('characters', []),
            'projectiles': game_state.get('projectiles', []),
            'weapons': game_state.get('weapons', []),
            'ammo_pickups': game_state.get('ammo_pickups', []),
            'platforms': game_state.get('platforms', [])
        }

        # Track which entities exist in the server snapshot
        current_entity_ids = set()

        # Process each entity type
        for entity_type, entities in server_entities.items():
            for entity_data in entities:
                network_id = entity_data.get('network_id')
                if network_id:
                    current_entity_ids.add(network_id)

                    # Update or create entity
                    if entity_type == 'platforms':
                        if network_id in self.platforms:
                            self._update_platform(network_id, entity_data)
                        else:
                            self._create_platform(network_id, entity_data)
                    else:
                        if network_id in self.entities:
                            self._update_entity(network_id, entity_data)
                        else:
                            self._create_entity(network_id, entity_data)

        # Remove entities that no longer exist on server
        entities_to_remove = []
        for network_id in self.entities:
            if network_id not in current_entity_ids:
                entities_to_remove.append(network_id)

        platforms_to_remove = []
        for network_id in self.platforms:
            if network_id not in current_entity_ids:
                platforms_to_remove.append(network_id)

        for network_id in entities_to_remove:
            self._remove_entity(network_id)

        for network_id in platforms_to_remove:
            self._remove_platform(network_id)

    def _create_entity(self, network_id: str, entity_data: dict):
        """Create a new entity from network data."""
        try:
            # Use the NetworkObject factory method to create the entity
            entity = NetworkObject.create_from_network_data(entity_data)

            if entity:
                # Initialize graphics for the new entity
                entity.init_graphics()
                self.entities[network_id] = entity

                # Initialize interpolation buffer
                self.interpolation_buffers[network_id] = deque(maxlen=self.max_buffer_size)


            else:
                # Entity type not handled
                pass

        except Exception as e:
            # Skip entities that fail to create
            pass

    def _update_entity(self, network_id: str, entity_data: dict):
        """Update an existing entity with new data."""
        if network_id not in self.entities:
            return

        entity = self.entities[network_id]

        # Add to interpolation buffer
        if network_id not in self.interpolation_buffers:
            self.interpolation_buffers[network_id] = deque(maxlen=self.max_buffer_size)

        buffer = self.interpolation_buffers[network_id]
        buffer.append({
            'data': entity_data,
            'timestamp': time.time()
        })

        # For local player, use direct server state (no prediction to avoid jitter)
        # For remote entities, apply interpolation for smooth movement
        if network_id == self.local_player_id:
            # Direct application of server state for local player
            for key, value in entity_data.items():
                if hasattr(entity, key) and key not in ['network_id', 'module_path', 'class_name', '_graphics_initialized']:
                    setattr(entity, key, value)
        else:
            self._interpolate_entity(entity, entity_data)

    def _interpolate_entity(self, entity, target_data: dict):
        """Apply smooth interpolation to remote entities."""
        buffer = self.interpolation_buffers.get(entity.network_id)
        if not buffer or len(buffer) < 2:
            # Not enough data for interpolation, apply directly
            for key, value in target_data.items():
                if hasattr(entity, key) and key not in ['network_id', 'module_path', 'class_name', '_graphics_initialized']:
                    setattr(entity, key, value)
            return

        # Get the two most recent snapshots
        snapshots = list(buffer)[-2:]
        older_snapshot = snapshots[0]
        newer_snapshot = snapshots[1]

        # Calculate interpolation factor (we want to be slightly behind for smoothness)
        time_diff = newer_snapshot['timestamp'] - older_snapshot['timestamp']
        if time_diff > 0:
            # Interpolate to a point 50ms in the past for smoothness
            interpolation_time = time.time() - 0.05
            t = min(1.0, max(0.0, (interpolation_time - older_snapshot['timestamp']) / time_diff))

            # Interpolate position
            if 'location' in older_snapshot['data'] and 'location' in newer_snapshot['data']:
                old_pos = older_snapshot['data']['location']
                new_pos = newer_snapshot['data']['location']
                interpolated_pos = [
                    old_pos[0] + (new_pos[0] - old_pos[0]) * t,
                    old_pos[1] + (new_pos[1] - old_pos[1]) * t
                ]
                entity.location = interpolated_pos

            # For other properties, use the newer snapshot
            for key, value in newer_snapshot['data'].items():
                if key not in ['network_id', 'module_path', 'class_name', '_graphics_initialized', 'location']:
                    if hasattr(entity, key):
                        setattr(entity, key, value)
        else:
            # Fallback to direct application
            for key, value in target_data.items():
                if hasattr(entity, key) and key not in ['network_id', 'module_path', 'class_name', '_graphics_initialized']:
                    setattr(entity, key, value)

    def _remove_entity(self, network_id: str):
        """Remove an entity that no longer exists."""
        if network_id in self.entities:
            del self.entities[network_id]
            if network_id in self.interpolation_buffers:
                del self.interpolation_buffers[network_id]

    def _create_platform(self, network_id: str, platform_data: dict):
        """Create a new platform from network data."""
        try:
            # Use the NetworkObject factory method to create the platform
            platform = NetworkObject.create_from_network_data(platform_data)

            if platform:
                # Initialize graphics for the new platform
                platform.init_graphics()
                self.platforms[network_id] = platform

            else:
                # Platform creation failed
                pass

        except Exception as e:
            # Skip platforms that fail to create
            pass

    def _update_platform(self, network_id: str, platform_data: dict):
        """Update an existing platform with new data."""
        if network_id not in self.platforms:
            return

        platform = self.platforms[network_id]

        # Check if position changed
        old_x = getattr(platform, 'float_x', 0)
        old_y = getattr(platform, 'float_y', 0)

        # Update platform data (platforms don't need interpolation typically)
        for key, value in platform_data.items():
            if hasattr(platform, key) and key not in ['network_id', 'module_path', 'class_name', '_graphics_initialized']:
                setattr(platform, key, value)

        # Update rect to match new position
        if hasattr(platform, 'float_x') and hasattr(platform, 'float_y'):
            platform.rect.x = int(platform.float_x)
            platform.rect.y = int(platform.float_y)

    def _remove_platform(self, network_id: str):
        """Remove a platform that no longer exists."""
        if network_id in self.platforms:
            del self.platforms[network_id]

    def get_entities_by_type(self, entity_type: type) -> List[Any]:
        """Get all entities of a specific type."""
        return [entity for entity in self.entities.values() if isinstance(entity, entity_type)]

    def get_entity(self, network_id: str) -> Optional[Any]:
        """Get a specific entity by network ID."""
        return self.entities.get(network_id)

    def draw_all(self, screen, arena_height: float):
        """Draw all entities and platforms."""
        # Draw platforms first (background)
        for platform in self.platforms.values():
            if hasattr(platform, 'draw'):
                platform.draw(screen, arena_height)

        # Draw entities (characters, projectiles, weapons)
        for entity in self.entities.values():
            if hasattr(entity, 'draw'):
                entity.draw(screen, arena_height)


def sync_game_files(files: dict):
    """
    Synchronize game files received from server.
    Overwrites local GameFolder files with server versions.
    """
    try:
        # Use main GameFolder at project root level, not BASE_files/GameFolder
        game_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "GameFolder")

        for filepath, content in files.items():
            # Ensure the path is within GameFolder
            if not filepath.startswith("GameFolder/"):
                continue

            full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), filepath)
            full_path = os.path.abspath(full_path)  # Normalize path

            # Security check: ensure it's within the GameFolder
            game_folder_abs = os.path.abspath(game_folder)
            if not full_path.startswith(game_folder_abs):
                continue

            # Create directory if needed
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # Write the file
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"Synchronized file: {filepath}")

        # Reload modules to pick up changes
        importlib.invalidate_caches()

        print("File synchronization complete")
        return True

    except Exception as e:
        return False
