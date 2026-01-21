#!/usr/bin/env python3
"""
Core Conflict Server - Authoritative Server Implementation

This server runs the game simulation without graphics and broadcasts game state to clients.
"""

import socket
import threading
import time
from datetime import datetime
import pickle
import os
import sys
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
import select
from BASE_files.BASE_menu_helpers import get_local_ip, encrypt_code
from BASE_files.server_state import ServerStateManager
from BASE_files.server_sync import ServerSyncManager

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure GameFolder exists and is importable before proceeding
from BASE_files.BASE_menu_helpers import ensure_gamefolder_exists
if not ensure_gamefolder_exists():
    print("Failed to restore GameFolder. Server cannot start.")
    sys.exit(1)

import GameFolder.setup

class GameServer:
    """
    Authoritative server that runs the game simulation and broadcasts state to clients.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 5555, practice_mode: bool = False):
        self.host = host
        self.port = port
        self.practice_mode = practice_mode
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

        # Auto-restart configuration
        self.restart_delay = 5.0  # seconds to wait before restart
        self.game_finished_time = 0.0
        self.waiting_for_restart = False

        # Empty server timeout configuration
        self.empty_server_timeout = 5.0  # seconds to wait with no clients before resetting
        self.last_client_disconnect_time = 0.0
        self.waiting_for_clients = False

        # File synchronization
        self.game_files = {}  # filename -> content

        # Patch synchronization for game start
        self.clients_patch_received: Set[str] = set()  # Track which clients have received patches
        self.clients_patch_ready: Set[str] = set()  # Track which clients have applied patches successfully
        self.clients_patch_failed: Dict[str, str] = {}  # Track which clients failed: player_id -> error_message
        self.waiting_for_patch_sync = False  # Flag to indicate we're waiting for patch sync
        self.waiting_for_patch_received = False  # Flag to indicate we're waiting for patch reception
        
        # File sync acknowledgment tracking (Fix #2: Game State Race Condition)
        self.clients_file_sync_ack: Set[str] = set()  # Track clients who finished reloading classes

        # Game state optimization and compatibility
        self.frame_counter = 0
        self.full_state_interval = 15
        self.static_update_interval = 10
        self.delta_excluded_fields = {
            'module_path',
            'class_name',
            'description',
            'primary_description',
            'passive_description',
        }
        self.client_state_cache: Dict[str, Dict[str, Dict[str, dict]]] = {}
        self.client_class_registry: Dict[str, Dict[int, Dict[str, str]]] = {}
        self.client_class_registry_reverse: Dict[str, Dict[Tuple[str, str], int]] = {}
        self.client_capabilities: Dict[str, dict] = {}
        self.pending_capabilities: Dict[socket.socket, dict] = {}
        self.requested_full_state: Set[str] = set()
        self.enable_compression = True
        self.enable_msgpack = True
        self.state_stats = {
            'full': {'raw': 0, 'compressed': 0, 'count': 0},
            'delta': {'raw': 0, 'compressed': 0, 'count': 0},
        }
        self.state_stats_log_interval = 300

        # Server-side patch management
        self.server_patches_dir = "__server_patches"
        os.makedirs(self.server_patches_dir, mode=0o755, exist_ok=True)
        self.client_patches: Dict[str, List[Dict]] = {}  # player_id -> list of patch info
        self.client_patch_files: Dict[str, Dict] = {}  # (player_id, patch_name) -> {'chunks': {}, 'total': N}
        self.clients_ready_status: Set[str] = set()  # Track which clients marked as ready
        self.client_backups: Dict[str, str] = {}  # player_id -> backup_name
        self.client_backup_transfers: Dict[str, Dict] = {}  # (player_id:backup_name) -> transfer info

        # Backup transfer tracking
        self.backup_transfer_in_progress = False
        self.backup_transfer_client = None
        self.backup_transfer_name = None
        self.backup_transfer_start_time = 0.0

        # Patch validation limits
        self.MAX_PATCHES_PER_CLIENT = 1  # Configurable limit, set to 1 for now

        # Managers
        self.state_manager = ServerStateManager(self)
        self.sync_manager = ServerSyncManager(self)
        self.sync_manager.load_game_files()

        print(f"Server initialized on {host}:{port}")
        if host == "0.0.0.0":
            # Local room - use actual local IP (auto-detects host IP in Docker)
            local_ip = get_local_ip()
            # Prefer CC_PUBLIC_IP; fall back to legacy GENGAME_PUBLIC_IP for compatibility
            public_ip_override = os.getenv("CC_PUBLIC_IP") or os.getenv("GENGAME_PUBLIC_IP")
            if public_ip_override:
                print(f"Using public IP override: {public_ip_override} (for room code generation)")
            elif os.path.exists("/.dockerenv"):
                if local_ip.startswith("172."):
                    print(f"⚠️  Docker detected but host IP auto-detection failed. Room code may not work from external devices.")
                    print(f"   Detected IP: {local_ip} (set CC_PUBLIC_IP=<your-host-ip> to fix)")
                else:
                    print(f"✓ Auto-detected host IP: {local_ip} (for room code generation)")
            else:
                print(f"Detected local IP: {local_ip} (for room code generation)")
            self.room_code = encrypt_code(local_ip, port, "LOCAL")
        else:
            # Remote room - use the host as domain
            self.room_code = encrypt_code(host, port, "REMOTE")

    def start(self):
        """Start the server."""
        self.running = True

        # Arena will be created dynamically when first client requests file sync
        # This allows us to create the arena with the correct number of connected players
        self.game_start_time = time.time()

        print(f"\n{'='*60}")
        print(f"🎮 ROOM CODE: {self.room_code}")
        print(f"{'='*60}\n")

        # Start network thread
        network_thread = threading.Thread(target=self._network_loop, daemon=True)
        network_thread.start()

        # Start game loop
        self._game_loop()

    def stop(self):
        """Stop the server."""
        self.running = False
        self.server_socket.close()
        # Create a copy of client sockets to avoid "dictionary changed size during iteration" error
        for client_socket in list(self.clients.values()):
            try:
                client_socket.close()
            except:
                pass
        print("Server stopped.")

    def _send_data_safe(self, client_socket: socket.socket, data: bytes):
        """Send data safely to a non-blocking socket by temporarily making it blocking."""
        was_blocking = client_socket.gettimeout() is not None
        try:
            client_socket.setblocking(True)
            client_socket.sendall(data)
        finally:
            client_socket.setblocking(False)

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

        # In practice mode, add a dummy AI player with unlimited lives
        if self.practice_mode and len(connected_player_names) == 1:
            # Add dummy AI player for practice mode
            connected_player_names.append("AI_Bot_Practice")
            print(f"Practice mode: Adding AI bot. Players: {connected_player_names}")
        else:
            print(f"Recreating arena with players: {connected_player_names}")

        try:
            # CRITICAL FIX: Always re-import setup to get the fresh module object after a reload!
            # The global 'GameFolder.setup' might point to the old module object.
            if 'GameFolder.setup' in sys.modules:
                # Force re-import to pick up new modules
                del sys.modules['GameFolder.setup']

            # Import fresh - this will also import any new modules
            import GameFolder.setup
            setup_module = GameFolder.setup

            # Recreate arena with actual player names
            world_width = getattr(setup_module, "WORLD_WIDTH", 1400)
            world_height = getattr(setup_module, "WORLD_HEIGHT", 900)
            self.arena = setup_module.setup_battle_arena(width=world_width, height=world_height, headless=True, player_names=connected_player_names)

            # In practice mode, disable game over checking
            if self.practice_mode:
                self.arena.practice_mode = True
                print("Practice mode: Game over checking disabled")

            # Set character IDs to match player names
            for i, character in enumerate(self.arena.characters):
                if i < len(connected_player_names):
                    player_name = connected_player_names[i]
                    character.id = player_name
                    # Keep display/name fields consistent across server + clients.
                    # Some client logic matches on `name`, while server-side control mapping uses `id`.
                    if hasattr(character, "name"):
                        character.name = player_name

                    # In practice mode, make AI bot have unlimited lives
                    if self.practice_mode and player_name == "AI_Bot_Practice":
                        # PRACTICE MODE ONLY: AI bot with unlimited lives for endless practice
                        # This special behavior only applies in practice mode - never in normal multiplayer
                        character.lives = float('inf')  # Unlimited lives

                        print("PRACTICE MODE: AI bot configured with unlimited lives (dies but respawns infinitely)")
                    
            print(f"[success] Arena recreated successfully with {len(self.arena.characters)} characters")
            
        except ImportError as e:
            print(f"[error] Failed to import game modules: {e}")
            import traceback
            traceback.print_exc()
            # Don't crash - just log the error
            raise
        except Exception as e:
            print(f"[error] Failed to recreate arena: {e}")
            import traceback
            traceback.print_exc()
            # Re-raise to let caller handle it
            raise

    def _recv_exact(self, socket, size: int) -> Optional[bytes]:
        """Receive exactly size bytes from non-blocking socket."""
        data = b''
        while len(data) < size:
            try:
                # Wait up to 5 seconds for data
                ready, _, _ = select.select([socket], [], [], 5.0)
                if ready:
                    chunk = socket.recv(size - len(data))
                    if not chunk:
                        return None # Disconnected
                    data += chunk
                else:
                    # Timeout waiting for data chunk - connection likely dead
                    print(f"Timeout waiting for data in _recv_exact (expected {size} bytes, got {len(data)})")
                    return None  # Return None instead of continuing forever
            except BlockingIOError:
                # Resource temporarily unavailable, try again
                continue
            except Exception as e:
                print(f"Error in _recv_exact: {e}")
                return None
        return data

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
                                if client_socket in self.pending_capabilities:
                                    del self.pending_capabilities[client_socket]
                                print(f"Pending client from {address} disconnected before sending player_name")
                        else:
                            # Regular client disconnected
                            self._handle_client_disconnect(player_id)
                        continue

                    message_length = int.from_bytes(length_bytes, byteorder='big')

                    # Receive the actual message using robust reader
                    data = self._recv_exact(client_socket, message_length)
                    
                    if data and len(data) == message_length:
                        message = pickle.loads(data)
                        self._process_client_message(player_id, message, client_socket)
                    else:
                        print(f"Failed to receive complete message body from {player_id}")
                        if not is_pending:
                            self._handle_client_disconnect(player_id)
                
                except BlockingIOError:
                    continue
                except Exception as e:
                    # Client likely disconnected
                    if is_pending:
                        # Pending client disconnected
                        if client_socket in self.pending_clients:
                            address = self.pending_clients[client_socket]
                            del self.pending_clients[client_socket]
                            if client_socket in self.pending_capabilities:
                                del self.pending_capabilities[client_socket]
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
            # Clean up player_name_to_id mapping (reverse lookup)
            names_to_remove = [name for name, pid in self.player_name_to_id.items() if pid == player_id]
            for name in names_to_remove:
                del self.player_name_to_id[name]
            
            # Fix #1: Cleanup synchronization states to prevent deadlocks
            self.clients_patch_received.discard(player_id)
            self.clients_patch_ready.discard(player_id)
            if player_id in self.clients_patch_failed:
                del self.clients_patch_failed[player_id]
            if hasattr(self, 'clients_file_sync_ack'):
                self.clients_file_sync_ack.discard(player_id)
            if player_id in self.clients_ready_status:
                self.clients_ready_status.discard(player_id)

            if player_id in self.client_state_cache:
                del self.client_state_cache[player_id]
            if player_id in self.client_class_registry:
                del self.client_class_registry[player_id]
            if player_id in self.client_class_registry_reverse:
                del self.client_class_registry_reverse[player_id]
            if player_id in self.client_capabilities:
                del self.client_capabilities[player_id]
            self.requested_full_state.discard(player_id)
            
            print(f"Client {player_id} disconnected")

            # Check if server is now empty
            if len(self.clients) == 0 and not self.waiting_for_clients:
                print(f"Server is now empty. Will reset to lobby in {self.empty_server_timeout} seconds if no one joins...")
                self.last_client_disconnect_time = time.time()
                self.waiting_for_clients = True

    def _process_client_message(self, player_id: str, message: dict, client_socket: socket.socket = None):
        """Process a message from a client."""
        msg_type = message.get('type', 'input')

        if msg_type == 'capabilities':
            caps = message.get('capabilities', message)
            if player_id == "pending" and client_socket in self.pending_clients:
                self.pending_capabilities[client_socket] = caps
            else:
                self.client_capabilities[player_id] = caps
            return
        if msg_type == 'request_full_state':
            self.requested_full_state.add(player_id)
            return
        if msg_type == 'input':
            # Add to input queue
            self.input_queues[player_id].append(message)
        elif msg_type == 'request_file_sync':
            # Client requested file synchronization
            # IMPORTANT: Do NOT create arena here - wait until client finishes reloading classes
            # This is because client and server share sys.modules when running in same process.
            # Send file_sync first, client will reload classes, then we create arena.
            
            # Always send file_sync to ensure client loads latest classes
            # This is safe now because game hasn't started yet
            self.sync_manager.send_file_sync(player_id)
        elif msg_type == 'request_start_game':
            # Client requested to start the game - send merge patch to all clients
            print(f"Player {player_id} requested to start game")
            self.sync_manager.initiate_game_start_with_patch_sync()
        elif msg_type == 'patch_received':
            # Client acknowledged that they've received the patch
            print(f"📦 {player_id} received the merge patch")

            if self.waiting_for_patch_received:
                self.clients_patch_received.add(player_id)

                # Check if all clients have received the patch
                all_clients = set(self.clients.keys())
                if self.clients_patch_received == all_clients:
                    print("[success] All clients have received the patch - now waiting for application")
                    self.waiting_for_patch_received = False
                    self.waiting_for_patch_sync = True
                    
                    # Fix #3: Check if everyone has ALREADY applied the patch (Race Condition Fix)
                    responded_clients = self.clients_patch_ready | set(self.clients_patch_failed.keys())
                    if responded_clients == all_clients:
                        print("Fast-track: All clients already ready, starting game...")
                        # Re-run the completion logic
                        if len(self.clients_patch_failed) == 0:
                            self._recreate_arena_with_players()
                            self.sync_manager.notify_all_clients_game_start()
                        else:
                            self.sync_manager.notify_patch_sync_failed()
        elif msg_type == 'patch_applied':
            # Client acknowledged that they've applied the patch
            patch_success = message.get('success', True)
            error_message = message.get('error', None)
            
            if patch_success:
                print(f"[success] {player_id} successfully applied the merge patch")
                self.clients_patch_ready.add(player_id)
            else:
                print(f"[error] {player_id} FAILED to apply the merge patch: {error_message}")
                self.clients_patch_failed[player_id] = error_message
            
            # Check if all clients have applied the patch (success or failure)
            all_clients = set(self.clients.keys())
            responded_clients = self.clients_patch_ready | set(self.clients_patch_failed.keys())

            if self.waiting_for_patch_sync and responded_clients == all_clients:
                print(f"\nPatch sync complete: {len(self.clients_patch_ready)} succeeded, {len(self.clients_patch_failed)} failed")
                
                # Only start game if ALL clients succeeded
                if len(self.clients_patch_failed) == 0:
                    print("[success] All clients ready - starting game!")
                    self.waiting_for_patch_received = False
                    self.waiting_for_patch_sync = False
                    self.clients_patch_received.clear()
                    self.clients_patch_ready.clear()
                    self._recreate_arena_with_players()  # CRITICAL: Recreate arena with NEW classes
                    self.sync_manager.notify_all_clients_game_start()
                else:
                    print("[error] Cannot start game - patch application failed on some clients:")
                    for failed_player, error in self.clients_patch_failed.items():
                        print(f"  - {failed_player}: {error}")
                    
                    # Notify all clients that game start was aborted
                    self.sync_manager.notify_patch_sync_failed()
                    
                    # Reset state
                    self.waiting_for_patch_received = False
                    self.waiting_for_patch_sync = False
                    self.clients_patch_received.clear()
                    self.clients_patch_ready.clear()
                    self.clients_patch_failed.clear()
        elif msg_type == 'file_sync_ack':
            # Client acknowledged file sync - NOW it's safe to create/recreate arena
            # because the client has reloaded its classes and updated sys.modules
            print(f"{player_id} acknowledged file sync")
            
            # Fix #2: Mark this client as ready for game state broadcasts
            self.clients_file_sync_ack.add(player_id)
            
            # Recreate arena with fresh classes from sys.modules
            # This ensures Character instances match the class in sys.modules
            if not hasattr(self, '_arena_initialized'):
                self._recreate_arena_with_players()
                self._arena_initialized = True
            else:
                # Already initialized - but if classes changed, we need to recreate
                # This handles the case where the client reconnects after game over
                # and triggers a reload that updates sys.modules
                pass  # For now, arena stays as is for returning players
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
                    if actual_player_id in self.clients or actual_player_id in self.player_name_to_id:
                        print(f"Player name '{requested_name}' already taken, rejecting")
                        # Send rejection message
                        response = {
                            'type': 'name_rejected',
                            'reason': 'Name already taken'
                        }
                        data = pickle.dumps(response)
                        length_bytes = len(data).to_bytes(4, byteorder='big')
                        try:
                            self._send_data_safe(client_socket, length_bytes + data)
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

                    if client_socket in self.pending_capabilities:
                        self.client_capabilities[actual_player_id] = self.pending_capabilities.pop(client_socket)

                    # Cancel empty server timeout since we now have clients
                    if self.waiting_for_clients:
                        print("Client joined - canceling empty server timeout")
                        self.waiting_for_clients = False
                        self.last_client_disconnect_time = 0.0

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
                    self._send_data_safe(self.clients[player_id], length_bytes + data)
                except Exception as e:
                    print(f"Failed to send character assignment: {e}")
        elif msg_type == 'file_request':
            # Client requesting a file
            self.sync_manager.handle_file_request(player_id, message)
        elif msg_type == 'file_chunk':
            # Client sending a file chunk - check if it's a backup chunk
            if message.get('is_backup', False):
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{timestamp}] 📦 ROUTING: Routing backup chunk {message.get('chunk_num', '?')} to _handle_backup_chunk")
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{timestamp}] 🔍 DEBUG SERVER: Received backup chunk from {player_id} - backup: {message.get('backup_name', 'unknown')}")
                self.sync_manager.handle_backup_chunk(player_id, message)
            else:
                print(f"📦 ROUTING: Routing regular file chunk to _handle_file_chunk")
                self.sync_manager.handle_file_chunk(player_id, message)
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

            # Server-side validation: Limit number of patches per client
            if len(patches) > self.MAX_PATCHES_PER_CLIENT:
                print(f"[security] {player_id} attempted to send {len(patches)} patches (max allowed: {self.MAX_PATCHES_PER_CLIENT})")
                self._send_message(player_id, {
                    'type': 'error',
                    'message': f'Too many patches selected. Maximum allowed: {self.MAX_PATCHES_PER_CLIENT}'
                })
                return

            self.client_patches[player_id] = patches

            # Extract backup name from first patch (all patches should have same base)
            backup_name = None
            if patches:
                backup_name = patches[0].get('base_backup')
                self.client_backups[player_id] = backup_name

            print(f"{player_id} selected {len(patches)} patch(es) from backup '{backup_name}'")
        elif msg_type == 'patch_chunk':
            # Client sending a patch file chunk
            self.sync_manager.handle_patch_chunk(player_id, message)
        elif msg_type == 'patches_ready':
            # Client marked patches as ready
            self.clients_ready_status.add(player_id)
            print(f"{player_id} marked as ready ({len(self.clients_ready_status)}/{len(self.clients)})")
            
            # Check if all clients are ready
            if self.clients_ready_status == set(self.clients.keys()):
                print("All clients ready - initiating patch merge and distribution")
                # Run patch merge in separate thread to avoid blocking network processing
                merge_thread = threading.Thread(target=self.sync_manager.merge_and_distribute_patches, daemon=True)
                merge_thread.start()

    def _send_message_to_client(self, player_id: str, message: dict):
        """Send a message to a specific client."""
        if player_id not in self.clients:
            print(f"[warning] MSG SEND: Cannot send message to {player_id} - client not found in self.clients")
            return

        try:
            data = pickle.dumps(message)
            length_bytes = len(data).to_bytes(4, byteorder='big')
            self._send_data_safe(self.clients[player_id], length_bytes + data)
            print(f"📤 MSG SEND: Successfully sent '{message.get('type', 'unknown')}' message to {player_id}")
        except Exception as e:
            print(f"[error] MSG SEND: Failed to send '{message.get('type', 'unknown')}' message to {player_id}: {e}")
            # Client might have disconnected
            self._remove_client(player_id)

    def _send_message(self, player_id: str, message: dict):
        """Compatibility wrapper for message sending."""
        self._send_message_to_client(player_id, message)

    def _remove_client(self, player_id: str):
        """Compatibility wrapper for client cleanup."""
        self._handle_client_disconnect(player_id)
    
    def _broadcast_game_state(self):
        """Broadcast the current game state to all clients."""
        self.state_manager.broadcast_game_state()

    def _game_loop(self):
        """Main game simulation loop with automatic restart."""
        print("Starting game simulation...")

        while self.running:
            current_time = time.time()

            # Check if we need to restart after game over (skip in practice mode)
            if self.waiting_for_restart and not self.practice_mode:
                if current_time - self.game_finished_time >= self.restart_delay:
                    self._restart_server()
                    continue

            # Check if game just finished (send restart message immediately)
            # Skip game over logic in practice mode
            if self.arena and self.arena.game_over and not self.waiting_for_restart and not self.practice_mode:
                self.game_finished_time = time.time()
                self.waiting_for_restart = True

                winner_name = self.arena.winner.id if self.arena.winner and hasattr(self.arena.winner, 'id') else "Unknown"
                print(f"\n🎉 GAME OVER! Winner: {winner_name}")
                print(f"🏆 Server will restart in {self.restart_delay} seconds...")

                # Send restart message to all clients
                restart_message = {
                    'type': 'game_restarting',
                    'winner': winner_name,
                    'restart_delay': self.restart_delay,
                    'message': f'Game finished! Winner: {winner_name}. Server restarting in {self.restart_delay} seconds...'
                }
                data = pickle.dumps(restart_message, protocol=4)
                length_bytes = len(data).to_bytes(4, byteorder='big')

                for player_id, client_socket in self.clients.items():
                    try:
                        self._send_data_safe(client_socket, length_bytes + data)
                        print(f"Sent restart notification to {player_id}")
                    except Exception as e:
                        print(f"Failed to send restart notification to {player_id}: {e}")

            # Check if server has been empty too long
            if self.waiting_for_clients and len(self.clients) == 0:
                if current_time - self.last_client_disconnect_time >= self.empty_server_timeout:
                    self._reset_empty_server()
                    continue

            # Fixed timestep game update
            if current_time - self.last_tick_time >= self.tick_interval:
                self._update_simulation(self.tick_interval)
                self._broadcast_game_state()
                self.last_tick_time = current_time

            # Sleep to prevent busy waiting
            time.sleep(0.001)

    def _restart_server(self):
        """Reset server state and notify clients to disconnect."""
        print("\n" + "="*50)
        print("GAME FINISHED - RESTARTING SERVER")
        print("="*50)

        # Disconnect all clients FIRST
        for player_id in list(self.clients.keys()):
            try:
                self.clients[player_id].close()
            except:
                pass

        # Reset all server state
        self.clients.clear()
        self.client_addresses.clear()
        self.input_queues.clear()
        self.last_input_ids.clear()
        self.player_name_to_id.clear()
        self.player_id_to_character.clear()
        self.pending_clients.clear()

        # Reset patch synchronization state
        self.clients_patch_received.clear()
        self.clients_patch_ready.clear()
        self.clients_patch_failed.clear()
        self.waiting_for_patch_sync = False
        self.waiting_for_patch_received = False
        self.client_patches.clear()
        self.client_patch_files.clear()
        self.clients_ready_status.clear()
        if hasattr(self, 'clients_file_sync_ack'):
            self.clients_file_sync_ack.clear()

        # CRITICAL: Restore GameFolder to base backup before resetting game state
        self.sync_manager.restore_gamefolder_to_base()

        # Reset game state
        self.arena = None
        self.game_start_time = time.time()
        self.waiting_for_restart = False
        self.game_finished_time = 0.0

        # Reset arena initialization flag
        if hasattr(self, '_arena_initialized'):
            delattr(self, '_arena_initialized')

        print("Server reset complete. All clients disconnected.")
        # Give clients time to detect disconnection before accepting new connections
        time.sleep(2.0)
        print("Players can now reconnect and start a new game.")

    def _reset_empty_server(self):
        """Reset server state when it's been empty for too long."""
        print("\n" + "="*60)
        print("SERVER EMPTY - RESETTING TO LOBBY")
        print("="*60)

        # Cancel empty server timeout
        self.waiting_for_clients = False
        self.last_client_disconnect_time = 0.0

        # Reset all server state (similar to restart but without disconnecting clients since there are none)
        self.input_queues.clear()
        self.last_input_ids.clear()
        self.player_name_to_id.clear()
        self.player_id_to_character.clear()
        self.pending_clients.clear()

        # Reset patch synchronization state
        self.clients_patch_received.clear()
        self.clients_patch_ready.clear()
        self.clients_patch_failed.clear()
        self.waiting_for_patch_sync = False
        self.waiting_for_patch_received = False
        self.client_patches.clear()
        self.client_patch_files.clear()
        self.clients_ready_status.clear()
        if hasattr(self, 'clients_file_sync_ack'):
            self.clients_file_sync_ack.clear()

        # CRITICAL: Restore GameFolder to base backup before resetting game state
        self.sync_manager.restore_gamefolder_to_base()

        # Reset game state
        self.arena = None
        self.game_start_time = time.time()
        self.waiting_for_restart = False
        self.game_finished_time = 0.0

        # Reset arena initialization flag
        if hasattr(self, '_arena_initialized'):
            delattr(self, '_arena_initialized')

        print("Server reset to lobby state. Waiting for players to join...")

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

        # Delegate input processing to the character itself.
        # This allows future agents to add new actions by only changing GAME_character.py
        # without needing to touch server.py.
        if hasattr(character, 'process_input'):
            character.process_input(input_data, self.arena)
        else:
            # Fallback for characters that haven't implemented it yet (though BaseCharacter has it now)
            pass

def main():
    """Main server entry point."""

    import argparse

    parser = argparse.ArgumentParser(description='Core Conflict Server')
    parser.add_argument('--host', default='0.0.0.0', help='Server host (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5555, help='Server port (default: 5555)')
    parser.add_argument('--practice', action='store_true', help='Enable practice mode (no auto-restart)')

    args = parser.parse_args()

    server = GameServer(args.host, args.port, practice_mode=args.practice)

    try:
        server.start()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.stop()


if __name__ == "__main__":
    main()
