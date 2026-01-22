#!/usr/bin/env python3
"""
Core Conflict Network Client - Handles connection to server and entity synchronization
"""

import socket
import threading
import time
import pickle
import zlib
import os
import sys
import importlib
import math
from typing import Dict, List, Optional, Callable, Any
from collections import deque
import select
from datetime import datetime

try:
    import msgpack
except ImportError:
    msgpack = None

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
        self.on_game_restarting = None
        self.on_server_restarted = None

        # Lag compensation
        self.last_server_time = 0.0
        self.latency = 0.0

        # File transfer state
        self.file_transfers = {}  # file_path -> {'chunks': {}, 'total_chunks': 0, 'received_chunks': 0}
        
        # File sync tracking
        self.file_sync_complete = False  # Track if file sync has completed
        self.file_sync_requested = False  # Track if we've requested sync

        # Capability advertisement for optimized state sync
        self.capabilities = {
            'protocol_version': 1,
            'supports_delta': True,
            'supports_compression': True,
            'supports_msgpack': msgpack is not None,
            'supports_static_cache': True,
        }

        self.debug_logging = bool(int(os.getenv("CC_NET_DEBUG", "0")))

        # Packet statistics tracking
        self.packet_stats = {
            'total_received': 0,
            'total_sent': 0,
            'received_timestamps': deque(maxlen=100),  # Keep last 100 timestamps for rolling window
            'sent_timestamps': deque(maxlen=100),
        }

    def connect(self, player_id: str) -> bool:
        """Connect to the server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.socket.setblocking(False)
            self.player_id = player_id
            self.connected = True
            self.running = True
            
            # Reset file sync flags for new connection
            self.file_sync_complete = False
            self.file_sync_requested = False

            # Start receive thread
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()

            print(f"Connected to server at {self.host}:{self.port} as {player_id}")

            # Send player name to server
            self._send_capabilities()
            self._send_player_name(player_id)

            return True

        except Exception as e:
            print(f"Failed to connect: {e}")
            return False

    def disconnect(self):
        """Disconnect from the server."""
        self.running = False
        self.connected = False
        
        # Reset file sync flags on disconnect
        self.file_sync_complete = False
        self.file_sync_requested = False

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

    def _send_capabilities(self):
        """Advertise client protocol capabilities to the server."""
        message = {
            'type': 'capabilities',
            'capabilities': self.capabilities,
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

    def request_full_state(self):
        """Request a full game state sync from the server."""
        if not self.connected:
            return
        message = {
            'type': 'request_full_state'
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

    def _queue_chunked_file(
        self,
        file_path: str,
        message_factory: Callable[[int, int, bytes], dict],
        on_chunk: Optional[Callable[[int, int, bytes], None]] = None,
        chunk_size: int = 64 * 1024,
        file_size: Optional[int] = None,
    ) -> int:
        """Queue a file for transfer in chunks and return total_chunks."""
        if file_size is None:
            file_size = os.path.getsize(file_path)
        total_chunks = (file_size + chunk_size - 1) // chunk_size

        with open(file_path, 'rb') as f:
            for chunk_num in range(total_chunks):
                chunk_data = f.read(chunk_size)
                message = message_factory(chunk_num, total_chunks, chunk_data)
                self.outgoing_queue.append(message)
                if on_chunk:
                    on_chunk(chunk_num, total_chunks, chunk_data)

        return total_chunks
    
    def _send_patch_file(self, file_path: str, patch_name: str):
        """Send a patch file to server in chunks."""
        try:
            def message_factory(chunk_num: int, total_chunks: int, chunk_data: bytes) -> dict:
                return {
                    'type': 'patch_chunk',
                    'patch_name': patch_name,
                    'chunk_num': chunk_num,
                    'total_chunks': total_chunks,
                    'data': chunk_data,
                    'player_id': self.player_id
                }

            total_chunks = self._queue_chunked_file(file_path, message_factory)
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
        
        # Mark file sync as complete
        self.file_sync_complete = True
        self.file_sync_requested = False  # Reset flag

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

            file_name = os.path.basename(file_path)
            target_path = target_path or file_name
            def message_factory(chunk_num: int, total_chunks: int, chunk_data: bytes) -> dict:
                return {
                    'type': 'file_chunk',
                    'file_path': target_path,
                    'chunk_num': chunk_num,
                    'total_chunks': total_chunks,
                    'data': chunk_data,
                    'player_id': self.player_id
                }

            def on_chunk(chunk_num: int, total_chunks: int, _chunk_data: bytes) -> None:
                if self.on_file_transfer_progress:
                    progress = (chunk_num + 1) / total_chunks
                    self.on_file_transfer_progress(target_path, progress, 'sending')

            self._queue_chunked_file(file_path, message_factory, on_chunk=on_chunk)
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

    def _recv_exact(self, size: int) -> Optional[bytes]:
        """Receive exactly size bytes from non-blocking socket."""
        data = b''
        while len(data) < size and self.running and self.connected:
            try:
                # Wait up to 5 seconds for data
                ready, _, _ = select.select([self.socket], [], [], 5.0)
                if ready:
                    chunk = self.socket.recv(size - len(data))
                    if not chunk:
                        return None # Disconnected
                    data += chunk
                else:
                    # Timeout waiting for data chunk
                    continue
            except BlockingIOError:
                # Resource temporarily unavailable, try again
                continue
            except Exception as e:
                print(f"Error in _recv_exact: {e}")
                return None
        return data

    def _maybe_request_file_sync(self, reason: str) -> bool:
        """Request file sync if we're missing it and haven't asked yet."""
        if self.file_sync_complete or self.file_sync_requested:
            return False
        print(f"{reason} - requesting file sync for recovery")
        self.file_sync_requested = True
        self.request_file_sync()
        return True

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

                    # Receive the actual message using robust reader
                    data = self._recv_exact(message_length)
                    
                    if data and len(data) == message_length:
                        try:
                            message = pickle.loads(data)
                            
                            # If this is game_state and file sync hasn't completed, skip it
                            if message.get('type') == 'game_state' and not self.file_sync_complete:
                                print("[warning] Received game_state before file sync complete - skipping")
                                self._maybe_request_file_sync("Received game_state before file sync complete")
                                continue
                            
                            self.incoming_queue.append(message)
                        except (pickle.UnpicklingError, EOFError, ValueError, UnicodeDecodeError) as pickle_error:
                            # Pickle or decode errors - likely class mismatch or data corruption
                            print(f"Failed to unpickle message: {type(pickle_error).__name__} (data length: {len(data)} bytes)")
                            
                            # If file sync hasn't completed, try requesting it as recovery
                            if self._maybe_request_file_sync("Unpickle error"):
                                continue
                            
                            self.disconnect()
                            break
                    else:
                        print("Failed to receive complete message body")
                        self.disconnect()
                        break

            except BlockingIOError:
                # Just continue if resource temp unavailable on length read
                continue
            except UnicodeDecodeError as decode_error:
                # Handle UTF-8 decode errors specifically
                print(f"Receive error: UnicodeDecodeError at position {decode_error.start}")
                # Try recovery if file sync hasn't completed
                if self._maybe_request_file_sync("UnicodeDecodeError"):
                    continue
                self.disconnect()
                break
            except Exception as e:
                if self.running:  # Only print error if we're supposed to be running
                    # Use type name and truncate message to avoid formatting binary data
                    error_msg = str(e)[:200] if len(str(e)) > 200 else str(e)
                    print(f"Receive error: {type(e).__name__}: {error_msg}")
                    self.disconnect()
                break

    def _send_data_safe(self, data: bytes):
        """Send data safely to a non-blocking socket by temporarily making it blocking."""
        if not self.socket:
            return
            
        was_blocking = self.socket.gettimeout() is not None
        try:
            self.socket.setblocking(True)
            self.socket.sendall(data)
        finally:
            self.socket.setblocking(False)

    def _send_outgoing_messages(self):
        """Send queued outgoing messages."""
        while self.outgoing_queue:
            try:
                message = self.outgoing_queue.popleft()
                msg_type = message.get('type', 'unknown')
                if self.debug_logging:
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] 📤 DEBUG CLIENT: Sending message type '{msg_type}' - queue size now: {len(self.outgoing_queue)}")
                    if msg_type == 'file_chunk' and message.get('is_backup'):
                        chunk_num = message.get('chunk_num', '?')
                        total_chunks = message.get('total_chunks', '?')
                        backup_name = message.get('backup_name', 'unknown')
                        print(f"[{timestamp}] 📤 DEBUG CLIENT: Sending backup chunk {chunk_num+1 if isinstance(chunk_num, int) else chunk_num}/{total_chunks} for '{backup_name}'")

                data = pickle.dumps(message, protocol=4)
                length_bytes = len(data).to_bytes(4, byteorder='big')
                self._send_data_safe(length_bytes + data)
                
                # Track sent packet (count input messages)
                if msg_type == 'input':
                    current_time = time.time()
                    self.packet_stats['sent_timestamps'].append(current_time)
                    self.packet_stats['total_sent'] += 1
                
                if self.debug_logging:
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] [success] DEBUG CLIENT: Successfully sent message type '{msg_type}'")
            except Exception as e:
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{timestamp}] [error] DEBUG CLIENT: Send error for message type '{message.get('type', 'unknown')}': {e}")
                self.disconnect()
                break

    def _process_incoming_messages(self):
        """Process received messages."""
        while self.incoming_queue:
            message = self.incoming_queue.popleft()
            self._handle_message(message)

    def _decode_game_state_payload(self, message: dict) -> Optional[dict]:
        payload = message.get('payload')
        if payload is None:
            return None

        data = payload
        if message.get('compressed'):
            try:
                data = zlib.decompress(payload)
            except Exception as e:
                print(f"[error] Failed to decompress game state payload: {e}")
                return None

        serialization = message.get('serialization', 'pickle')
        try:
            if serialization == 'msgpack':
                if msgpack is None:
                    print("[error] Msgpack payload received but msgpack is unavailable")
                    return None
                return msgpack.unpackb(data, raw=False, strict_map_key=False)
            return pickle.loads(data)
        except Exception as e:
            print(f"[error] Failed to decode game state payload ({serialization}): {e}")
            return None

    def _handle_message(self, message: dict):
        """Handle a received message."""
        msg_type = message.get('type')

        # Debug: Log all received messages
        if self.debug_logging:
            print(f"📨 CLIENT MSG: Received message type '{msg_type}' from server")

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
            # Track received packet - only count game_state messages
            current_time = time.time()
            self.packet_stats['received_timestamps'].append(current_time)
            self.packet_stats['total_received'] += 1
            
            game_state = message
            if 'payload' in message:
                decoded = self._decode_game_state_payload(message)
                if decoded is None:
                    print("[warning] Game state decode failed - requesting full state")
                    self.request_full_state()
                    return
                decoded['_message_type'] = message.get('message_type', 1)
                game_state = decoded
            else:
                game_state['_message_type'] = message.get('message_type', 1)
            if self.on_game_state_received:
                self.on_game_state_received(game_state)
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
            print(f"[error] Patch sync failed: {reason}")
            print(f"Failed clients: {', '.join(failed_clients)}")
            for detail in details:
                print(f"  - {detail}")
            if self.on_patch_sync_failed:
                self.on_patch_sync_failed(reason, failed_clients, details)
        elif msg_type == 'patch_merge_failed':
            reason = message.get('reason', 'Unknown reason')
            print(f"[error] Patch merge failed on server: {reason}")
            if self.on_patch_merge_failed:
                self.on_patch_merge_failed(reason)
        elif msg_type == 'game_restarting':
            winner = message.get('winner', 'Unknown')
            restart_delay = message.get('restart_delay', 5.0)
            msg = message.get('message', f'Game restarting in {restart_delay} seconds...')
            print(f"🏆 Game finished! Winner: {winner}")
            print(f"🔄 {msg}")
            if self.on_game_restarting:
                self.on_game_restarting(winner, restart_delay, msg)
        elif msg_type == 'server_restarted':
            msg = message.get('message', 'Server has restarted.')
            print(f"🔄 {msg}")
            if self.on_server_restarted:
                self.on_server_restarted(msg)
        elif msg_type == 'backup_transfer_success':
            backup_name = message.get('backup_name')
            print(f"🎉 BACKUP ACK: Server confirmed backup '{backup_name}' received and extracted successfully!")
        elif msg_type == 'backup_transfer_failed':
            backup_name = message.get('backup_name')
            error = message.get('error', 'Unknown error')
            print(f"💥 BACKUP ACK: Server reported backup '{backup_name}' transfer/extraction failed: {error}")
        elif msg_type == 'request_backup':
            backup_name = message.get('backup_name')
            print(f"🔄 BACKUP REQUEST: Client received backup request for '{backup_name}'")
            if backup_name:
                if self.debug_logging:
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] 📤 BACKUP REQUEST: Client calling _send_backup_to_server for '{backup_name}'")
                    print(f"[{timestamp}] 🔍 DEBUG CLIENT: About to call _send_backup_to_server")
                self._send_backup_to_server(backup_name)
                if self.debug_logging:
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] 🔍 DEBUG CLIENT: _send_backup_to_server completed")
            else:
                print(f"[error] BACKUP REQUEST: Invalid backup request - no backup_name provided")

    def _send_backup_to_server(self, backup_name: str):
        """Send a backup folder to the server."""
        try:
            import os
            cwd = os.getcwd()
            print(f"📍 BACKUP SEND: Current working directory: {cwd}")

            backup_path = f"__game_backups/{backup_name}"
            abs_backup_path = os.path.abspath(backup_path)
            print(f"📍 BACKUP SEND: Looking for backup at: {abs_backup_path}")

            if not os.path.exists(backup_path):
                print(f"[error] BACKUP SEND: Backup {backup_name} not found locally at {backup_path}")
                print(f"[error] BACKUP SEND: Absolute path: {abs_backup_path}")
                # List contents of __game_backups if it exists
                game_backups_dir = "__game_backups"
                if os.path.exists(game_backups_dir):
                    contents = os.listdir(game_backups_dir)
                    print(f"[error] BACKUP SEND: Contents of __game_backups: {contents}")
                else:
                    print(f"[error] BACKUP SEND: __game_backups directory does not exist")
                return

            print(f"[success] BACKUP SEND: Found backup '{backup_name}' at {backup_path}")
            print(f"📤 BACKUP SEND: Starting to send backup '{backup_name}' from {backup_path}")

            # Create a temporary compressed archive
            import tempfile
            import tarfile
            import gzip

            with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as temp_file:
                temp_path = temp_file.name

            # Create compressed tar archive
            with tarfile.open(temp_path, 'w:gz') as tar:
                tar.add(backup_path, arcname=backup_name)

            # Calculate total chunks BEFORE sending any chunks
            chunk_size = 64 * 1024  # 64KB chunks
            file_size = os.path.getsize(temp_path)
            total_chunks = (file_size + chunk_size - 1) // chunk_size

            print(f"📦 BACKUP SEND: Compressed '{backup_name}' to {file_size} bytes, will send in {total_chunks} chunks")

            def message_factory(chunk_num: int, total_chunks: int, chunk_data: bytes) -> dict:
                return {
                    'type': 'file_chunk',
                    'backup_name': backup_name,
                    'chunk_num': chunk_num,
                    'total_chunks': total_chunks,
                    'data': chunk_data,
                    'is_backup': True
                }

            def on_chunk(chunk_num: int, total_chunks: int, chunk_data: bytes) -> None:
                progress = (chunk_num + 1) / total_chunks * 100
                if self.debug_logging:
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] 📤 BACKUP SEND: Queued chunk {chunk_num+1}/{total_chunks} ({progress:.1f}%) for '{backup_name}' - data size: {len(chunk_data)} bytes")
                    print(f"[{timestamp}] 🔍 DEBUG CLIENT: Outgoing queue now has {len(self.outgoing_queue)} messages")

            self._queue_chunked_file(
                temp_path,
                message_factory,
                on_chunk=on_chunk,
                chunk_size=chunk_size,
                file_size=file_size,
            )

            print(f"[success] BACKUP SEND: Successfully queued all {total_chunks} chunks for backup '{backup_name}' to server")

            # Clean up temp file
            os.unlink(temp_path)

        except Exception as e:
            print(f"[error] BACKUP SEND: Failed to send backup {backup_name}: {e}")

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

    def _queue_file_ack(self, file_path: str, success: bool, error: Optional[str] = None):
        message = {
            'type': 'file_ack',
            'file_path': file_path,
            'player_id': self.player_id,
            'success': success
        }
        if error:
            message['error'] = error
        self.outgoing_queue.append(message)

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
            self._queue_file_ack(file_path, True)

            # Call completion callback
            if self.on_file_received:
                self.on_file_received(file_path, True)

            print(f"File received successfully: {file_path}")

        except Exception as e:
            print(f"Failed to assemble file {file_path}: {e}")

            # Send failure acknowledgment
            self._queue_file_ack(file_path, False, str(e))

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

    def get_packet_stats(self) -> dict:
        """Get current packet statistics using rolling 1-second window."""
        current_time = time.time()
        one_second_ago = current_time - 1.0
        
        # Count packets received in the last second (only game_state messages)
        received_last_second = sum(1 for ts in self.packet_stats['received_timestamps'] 
                                   if ts >= one_second_ago)
        
        # Count packets sent in the last second (only input messages)
        sent_last_second = sum(1 for ts in self.packet_stats['sent_timestamps'] 
                              if ts >= one_second_ago)
        
        return {
            'received_last_second': received_last_second,
            'total_received': self.packet_stats['total_received'],
            'total_sent': self.packet_stats['total_sent'],
            'packets_lost': max(0, self.packet_stats['total_sent'] - self.packet_stats['total_received'])
        }


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
        self.class_registry: Dict[int, Dict[str, str]] = {}
        self.entity_class_map: Dict[str, int] = {}

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
        message_type = game_state.get('_message_type', game_state.get('message_type', 1))
        class_registry = game_state.get('class_registry')
        if class_registry:
            self.class_registry = class_registry

        server_entities = {
            'characters': game_state.get('characters', []),
            'projectiles': game_state.get('projectiles', []),
            'weapons': game_state.get('weapons', []),
            'ammo_pickups': game_state.get('ammo_pickups', []),
            'platforms': game_state.get('platforms', [])
        }

        removed_entities = game_state.get('removed_entities', [])
        if message_type == 0 and removed_entities:
            for network_id in removed_entities:
                if network_id in self.platforms:
                    self._remove_platform(network_id)
                if network_id in self.entities:
                    self._remove_entity(network_id)
                if network_id in self.entity_class_map:
                    del self.entity_class_map[network_id]

        # Full state replaces everything.
        if message_type == 1:
            current_entity_ids = set()
            for entity_type, entities in server_entities.items():
                entities = entities or []
                for entity_data in entities:
                    network_id = entity_data.get('network_id')
                    if not network_id:
                        continue
                    current_entity_ids.add(network_id)
                    class_id = entity_data.get('class_id')
                    if class_id is not None:
                        self.entity_class_map[network_id] = class_id

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
                if network_id in self.entity_class_map:
                    del self.entity_class_map[network_id]

            for network_id in platforms_to_remove:
                self._remove_platform(network_id)
                if network_id in self.entity_class_map:
                    del self.entity_class_map[network_id]
            return

        # Delta updates only apply changes; skip missing entity lists.
        for entity_type, entities in server_entities.items():
            if entities is None:
                continue
            for entity_data in entities:
                network_id = entity_data.get('network_id')
                if not network_id:
                    continue
                class_id = entity_data.get('class_id')
                if class_id is not None:
                    self.entity_class_map[network_id] = class_id

                if entity_type == 'platforms':
                    if network_id in self.platforms:
                        self._update_platform(network_id, entity_data)
                    else:
                        if not self._create_platform(network_id, entity_data):
                            raise ValueError("Missing metadata for platform creation")
                else:
                    if network_id in self.entities:
                        self._update_entity(network_id, entity_data)
                    else:
                        if not self._create_entity(network_id, entity_data):
                            raise ValueError("Missing metadata for entity creation")

    def _resolve_entity_metadata(self, entity_data: dict) -> dict:
        if entity_data.get('module_path') and entity_data.get('class_name'):
            return entity_data
        class_id = entity_data.get('class_id') or self.entity_class_map.get(entity_data.get('network_id'))
        if class_id and class_id in self.class_registry:
            resolved = dict(entity_data)
            meta = self.class_registry[class_id]
            resolved.setdefault('module_path', meta.get('module_path'))
            resolved.setdefault('class_name', meta.get('class_name'))
            resolved['class_id'] = class_id
            return resolved
        return entity_data

    def _create_entity(self, network_id: str, entity_data: dict):
        """Create a new entity from network data."""
        try:
            # Use the NetworkObject factory method to create the entity
            resolved = self._resolve_entity_metadata(entity_data)
            if not resolved.get('module_path') or not resolved.get('class_name'):
                return False

            entity = NetworkObject.create_from_network_data(resolved)

            if entity:
                # Initialize graphics for the new entity
                entity.init_graphics()
                self.entities[network_id] = entity
                class_id = resolved.get('class_id')
                if class_id is not None:
                    self.entity_class_map[network_id] = class_id

                # Initialize interpolation buffer
                self.interpolation_buffers[network_id] = deque(maxlen=self.max_buffer_size)


            else:
                # Entity type not handled
                return False

        except Exception as e:
            # Skip entities that fail to create
            return False
        return True

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
        if network_id in self.entity_class_map:
            del self.entity_class_map[network_id]

    def _create_platform(self, network_id: str, platform_data: dict):
        """Create a new platform from network data."""
        try:
            # Use the NetworkObject factory method to create the platform
            resolved = self._resolve_entity_metadata(platform_data)
            if not resolved.get('module_path') or not resolved.get('class_name'):
                return False

            platform = NetworkObject.create_from_network_data(resolved)

            if platform:
                # Initialize graphics for the new platform
                platform.init_graphics()
                self.platforms[network_id] = platform
                class_id = resolved.get('class_id')
                if class_id is not None:
                    self.entity_class_map[network_id] = class_id

            else:
                # Platform creation failed
                return False

        except Exception as e:
            # Skip platforms that fail to create
            return False
        return True

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
        if network_id in self.entity_class_map:
            del self.entity_class_map[network_id]


    def get_entities_by_type(self, entity_type: type) -> List[Any]:
        """Get all entities of a specific type."""
        return [entity for entity in self.entities.values() if isinstance(entity, entity_type)]

    def get_entity(self, network_id: str) -> Optional[Any]:
        """Get a specific entity by network ID."""
        return self.entities.get(network_id)
        
    def clear(self):
        """Clear all entities and state."""
        self.entities.clear()
        self.platforms.clear()
        self.interpolation_buffers.clear()
        self.class_registry.clear()
        self.entity_class_map.clear()

    def draw_all(self, screen, arena_height: float, camera=None):
        """Draw all entities and platforms."""
        screen_bounds = None
        if camera is not None:
            min_dim = min(screen.get_width(), screen.get_height())
            margin = max(64, int(min_dim * 0.12))
            screen_bounds = (
                -margin,
                -margin,
                screen.get_width() + margin,
                screen.get_height() + margin,
            )

        def bounds_intersect(a, b):
            return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])

        def get_entity_bounds(entity):
            if camera is None:
                rect = None
                if hasattr(entity, "get_rect"):
                    try:
                        rect = entity.get_rect(arena_height)
                    except Exception:
                        rect = None
                if rect is None and hasattr(entity, "rect"):
                    rect = entity.rect
                if rect is None:
                    return None
                return (rect.left, rect.top, rect.right, rect.bottom)

            rect = None
            if hasattr(entity, "get_draw_rect"):
                try:
                    rect = entity.get_draw_rect(arena_height, camera)
                except Exception:
                    rect = None
            if rect is not None:
                return (rect.left, rect.top, rect.right, rect.bottom)

            location = getattr(entity, "location", None)
            if location is not None:
                if hasattr(entity, "width") and hasattr(entity, "height"):
                    center = camera.world_to_screen_point(location[0], location[1])
                    half_w = float(entity.width) / 2.0
                    half_h = float(entity.height) / 2.0
                    return (
                        center[0] - half_w,
                        center[1] - half_h,
                        center[0] + half_w,
                        center[1] + half_h,
                    )
                if hasattr(entity, "radius"):
                    radius = float(entity.radius)
                    center = camera.world_to_screen_point(location[0], location[1])
                    return (
                        center[0] - radius,
                        center[1] - radius,
                        center[0] + radius,
                        center[1] + radius,
                    )
                if hasattr(entity, "length") and hasattr(entity, "width") and hasattr(entity, "angle"):
                    start = (location[0], location[1])
                    end = (
                        location[0] + float(entity.length) * math.cos(entity.angle),
                        location[1] + float(entity.length) * math.sin(entity.angle),
                    )
                    start_s = camera.world_to_screen_point(start[0], start[1])
                    end_s = camera.world_to_screen_point(end[0], end[1])
                    pad = float(entity.width) / 2.0
                    min_x = min(start_s[0], end_s[0]) - pad
                    max_x = max(start_s[0], end_s[0]) + pad
                    min_y = min(start_s[1], end_s[1]) - pad
                    max_y = max(start_s[1], end_s[1]) + pad
                    return (min_x, min_y, max_x, max_y)
                if hasattr(entity, "height") and hasattr(entity, "base") and hasattr(entity, "angle"):
                    p1_x, p1_y = location[0], location[1]
                    p2_x = p1_x + float(entity.height) * math.cos(entity.angle)
                    p2_y = p1_y + float(entity.height) * math.sin(entity.angle)
                    p3_x = p2_x - float(entity.base) * 0.5 * math.sin(entity.angle)
                    p3_y = p2_y + float(entity.base) * 0.5 * math.cos(entity.angle)
                    p4_x = p2_x + float(entity.base) * 0.5 * math.sin(entity.angle)
                    p4_y = p2_y - float(entity.base) * 0.5 * math.cos(entity.angle)
                    points = (
                        camera.world_to_screen_point(p1_x, p1_y),
                        camera.world_to_screen_point(p3_x, p3_y),
                        camera.world_to_screen_point(p4_x, p4_y),
                    )
                    min_x = min(p[0] for p in points)
                    max_x = max(p[0] for p in points)
                    min_y = min(p[1] for p in points)
                    max_y = max(p[1] for p in points)
                    return (min_x, min_y, max_x, max_y)

            world_center = getattr(entity, "world_center", None)
            if world_center is not None:
                if hasattr(entity, "size"):
                    size = float(entity.size)
                    center = camera.world_to_screen_point(world_center[0], world_center[1])
                    half = size / 2.0
                    return (
                        center[0] - half,
                        center[1] - half,
                        center[0] + half,
                        center[1] + half,
                    )
                if hasattr(entity, "radius"):
                    radius = float(entity.radius)
                    center = camera.world_to_screen_point(world_center[0], world_center[1])
                    return (
                        center[0] - radius,
                        center[1] - radius,
                        center[0] + radius,
                        center[1] + radius,
                    )

            return None

        def is_visible(entity):
            if getattr(entity, "always_visible", False):
                return True
            if screen_bounds is None:
                return True
            bounds = get_entity_bounds(entity)
            if bounds is None:
                return True
            return bounds_intersect(bounds, screen_bounds)

        # Draw platforms first (background)
        for platform in self.platforms.values():
            if hasattr(platform, 'draw'):
                if not is_visible(platform):
                    continue
                platform.draw(screen, arena_height, camera=camera)

        # Draw entities (characters, projectiles, weapons)
        for entity in self.entities.values():
            if hasattr(entity, 'draw'):
                if not is_visible(entity):
                    continue
                entity.draw(screen, arena_height, camera=camera)


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
