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
import glob
import importlib
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
import select
from BASE_files.BASE_menu_helpers import reload_game_code, get_local_ip, encrypt_code

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure GameFolder exists and is importable before proceeding
from BASE_files.BASE_menu_helpers import ensure_gamefolder_exists
if not ensure_gamefolder_exists():
    print("Failed to restore GameFolder. Server cannot start.")
    sys.exit(1)

import GameFolder.setup
from coding.non_callable_tools.version_control import VersionControl
from coding.tools.conflict_resolution import get_all_conflicts
from agent import auto_fix_conflicts
from BASE_files.BASE_menu_helpers import load_settings

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
        self._load_game_files()

        # Patch synchronization for game start
        self.clients_patch_received: Set[str] = set()  # Track which clients have received patches
        self.clients_patch_ready: Set[str] = set()  # Track which clients have applied patches successfully
        self.clients_patch_failed: Dict[str, str] = {}  # Track which clients failed: player_id -> error_message
        self.waiting_for_patch_sync = False  # Flag to indicate we're waiting for patch sync
        self.waiting_for_patch_received = False  # Flag to indicate we're waiting for patch reception
        
        # File sync acknowledgment tracking (Fix #2: Game State Race Condition)
        self.clients_file_sync_ack: Set[str] = set()  # Track clients who finished reloading classes

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

    def _restore_gamefolder_to_base(self):
        """Restore GameFolder to the base backup and clear module cache."""
        try:
            from coding.non_callable_tools.backup_handling import BackupHandler
            import traceback
            
            backup_handler = BackupHandler("__game_backups")
            backups = backup_handler.list_backups()
            
            if not backups:
                print("[warning] No backups available to restore from. GameFolder will remain in current state.")
                return
            
            # Sort backups by modification time (most recent first)
            backups_with_mtime = [(b, os.path.getmtime(os.path.join("__game_backups", b))) for b in backups]
            backups_with_mtime.sort(key=lambda x: x[1], reverse=True)
            base_backup = backups_with_mtime[0][0]
            
            print(f"Restoring GameFolder to base backup: {base_backup}")
            success, _ = backup_handler.restore_backup(base_backup, target_path="GameFolder")
            
            if success:
                print(f"[success] GameFolder restored to base backup: {base_backup}")
                
                # Clear Python module cache for GameFolder modules
                modules_to_clear = [key for key in list(sys.modules.keys()) if key.startswith('GameFolder')]
                for module_name in modules_to_clear:
                    try:
                        del sys.modules[module_name]
                    except KeyError:
                        pass
                importlib.invalidate_caches()
                print(f"[success] Cleared {len(modules_to_clear)} cached GameFolder modules")
                
                # Reload game files after restore
                self._load_game_files()
                
                # Clear any cached merged patch file
                merged_patch_path = os.path.join(self.server_patches_dir, "merged_patch.json")
                if os.path.exists(merged_patch_path):
                    os.remove(merged_patch_path)
                    print("[success] Cleared old merged_patch.json file")
            else:
                print(f"[warning] Failed to restore GameFolder to base backup: {base_backup}")
        except Exception as e:
            print(f"[error] Error restoring GameFolder to base backup: {e}")
            import traceback
            traceback.print_exc()

    def _get_available_backups(self) -> set:
        """Get set of backup names server has available."""
        backup_dir = "__game_backups"
        if not os.path.exists(backup_dir):
            return set()
        return {d for d in os.listdir(backup_dir) if os.path.isdir(os.path.join(backup_dir, d))}

    def _request_backup_from_client(self, player_id: str, backup_name: str):
        """Request backup transfer from client."""
        message = {
            'type': 'request_backup',
            'backup_name': backup_name
        }
        self._send_message_to_client(player_id, message)
        print(f"📨 BACKUP REQUEST: Server sent backup request to client '{player_id}' for backup '{backup_name}'")

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
            print(f"[warning]  Found {len(patch_files)} patches:")
            for pf in patch_files:
                print(f"    - {os.path.basename(pf)}")
            print(f"[warning]  Using only first patch: {os.path.basename(patch_files[0])}")
            print(f"[warning]  TODO: Implement proper 3-way merge using VersionControl.merge_patches()")
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
            self._send_data_safe(client_socket, length_bytes + data)
            
            print(f"Sent merge patch to {player_id} ({len(patch_content)} bytes)")
        except Exception as e:
            print(f"Failed to send patch to {player_id}: {e}")

    def _notify_all_clients_game_start(self):
        """Notify all connected clients to start the game."""
        print("Notifying all clients to start game...")
        
        # Fix #2: Reset file sync ACK tracker when starting new game
        self.clients_file_sync_ack.clear()

        message = {
            'type': 'game_start'
        }
        data = pickle.dumps(message)
        length_bytes = len(data).to_bytes(4, byteorder='big')

        for player_id, client_socket in self.clients.items():
            try:
                self._send_data_safe(client_socket, length_bytes + data)
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
                self._send_data_safe(client_socket, length_bytes + data)
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
            self._send_data_safe(client_socket, length_bytes + data)

            print(f"Sent file sync to {player_id}")

        except Exception as e:
            print(f"Failed to send file sync to {player_id}: {e}")

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
            
            print(f"Client {player_id} disconnected")

            # Check if server is now empty
            if len(self.clients) == 0 and not self.waiting_for_clients:
                print(f"Server is now empty. Will reset to lobby in {self.empty_server_timeout} seconds if no one joins...")
                self.last_client_disconnect_time = time.time()
                self.waiting_for_clients = True

    def _process_client_message(self, player_id: str, message: dict, client_socket: socket.socket = None):
        """Process a message from a client."""
        msg_type = message.get('type', 'input')

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
                            self._notify_all_clients_game_start()
                        else:
                            self._notify_patch_sync_failed()
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
                    self._notify_all_clients_game_start()
                else:
                    print("[error] Cannot start game - patch application failed on some clients:")
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
            self._handle_file_request(player_id, message)
        elif msg_type == 'file_chunk':
            # Client sending a file chunk - check if it's a backup chunk
            if message.get('is_backup', False):
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{timestamp}] 📦 ROUTING: Routing backup chunk {message.get('chunk_num', '?')} to _handle_backup_chunk")
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{timestamp}] 🔍 DEBUG SERVER: Received backup chunk from {player_id} - backup: {message.get('backup_name', 'unknown')}")
                self._handle_backup_chunk(player_id, message)
            else:
                print(f"📦 ROUTING: Routing regular file chunk to _handle_file_chunk")
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
            self._handle_patch_chunk(player_id, message)
        elif msg_type == 'patches_ready':
            # Client marked patches as ready
            self.clients_ready_status.add(player_id)
            print(f"{player_id} marked as ready ({len(self.clients_ready_status)}/{len(self.clients)})")
            
            # Check if all clients are ready
            if self.clients_ready_status == set(self.clients.keys()):
                print("All clients ready - initiating patch merge and distribution")
                # Run patch merge in separate thread to avoid blocking network processing
                merge_thread = threading.Thread(target=self._merge_and_distribute_patches, daemon=True)
                merge_thread.start()

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
        is_backup = message.get('is_backup', False)

        if not all([file_path, isinstance(chunk_num, int), isinstance(total_chunks, int), chunk_data]):
            print(f"Invalid file chunk from {player_id}")
            return

        # Handle backup transfers differently
        if is_backup:
            self._handle_backup_chunk(player_id, message)
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

    def _handle_backup_chunk(self, player_id: str, message: dict):
        """Handle a backup file chunk received from a client."""
        backup_name = message.get('backup_name')
        chunk_num = message.get('chunk_num')
        total_chunks = message.get('total_chunks')
        chunk_data = message.get('data')

        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"[{timestamp}] 📦 BACKUP CHUNK: Received chunk {chunk_num+1 if isinstance(chunk_num, int) else '?'} from {player_id} for '{backup_name}'")
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"[{timestamp}] 🔍 DEBUG: Message details - backup: {backup_name}, chunk: {chunk_num}/{total_chunks}, data_size: {len(chunk_data) if chunk_data else 0} bytes")
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"[{timestamp}] 🔍 DEBUG: Current transfer state - in_progress: {getattr(self, 'backup_transfer_in_progress', False)}, expected_backup: {getattr(self, 'backup_transfer_name', 'None')}")

        if not all([backup_name, isinstance(chunk_num, int), isinstance(total_chunks, int), chunk_data]):
            print(f"[error] BACKUP CHUNK: Invalid backup chunk from {player_id}: missing or invalid fields")
            return

        # Reject invalid total_chunks
        if total_chunks <= 0:
            print(f"[error] BACKUP CHUNK: Invalid total_chunks {total_chunks} from {player_id}")
            return

        # Validate chunk_num bounds
        if chunk_num < 0 or chunk_num >= total_chunks:
            print(f"[error] BACKUP CHUNK: Invalid chunk_num {chunk_num} (should be 0-{total_chunks-1}) from {player_id}")
            return

        # Initialize backup transfer tracking if needed
        if not hasattr(self, 'client_backup_transfers'):
            self.client_backup_transfers = {}

        client_key = f"{player_id}:{backup_name}"
        if client_key not in self.client_backup_transfers:
            print(f"📁 BACKUP CHUNK: Starting new transfer for '{backup_name}' from {player_id} ({total_chunks} chunks total)")
            self.client_backup_transfers[client_key] = {
                'chunks': {},
                'total_chunks': total_chunks,
                'received_chunks': 0
            }

        transfer = self.client_backup_transfers[client_key]

        # Store chunk if not already received
        if chunk_num not in transfer['chunks']:
            transfer['chunks'][chunk_num] = chunk_data
            transfer['received_chunks'] += 1
            progress = transfer['received_chunks'] / total_chunks * 100
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"[{timestamp}] [success] BACKUP CHUNK: Stored chunk {chunk_num+1}/{total_chunks} ({progress:.1f}%) for '{backup_name}' from {player_id}")
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"[{timestamp}] 📊 DEBUG: Chunk received - backup: {backup_name}, received: {transfer['received_chunks']}/{total_chunks}")
        else:
            print(f"[warning] BACKUP CHUNK: Duplicate chunk {chunk_num} for '{backup_name}' from {player_id}")

        # Check if backup is complete
        if transfer['received_chunks'] == total_chunks:
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"[{timestamp}] 🎯 BACKUP CHUNK: All {total_chunks} chunks received for '{backup_name}' from {player_id}, starting assembly...")
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"[{timestamp}] 🔄 DEBUG: Starting backup assembly for {backup_name}")
            success = self._assemble_client_backup(player_id, backup_name)
            if success:
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{timestamp}] [success] DEBUG: Backup assembly successful for {backup_name}")
                if hasattr(self, 'backup_transfer_in_progress') and self.backup_transfer_in_progress:
                    if backup_name == getattr(self, 'backup_transfer_name', None):
                        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                        print(f"[{timestamp}] 🎉 BACKUP TRANSFER: Successfully completed transfer of '{backup_name}'")
                        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                        print(f"[{timestamp}] 🚩 DEBUG: Setting backup_transfer_complete_event for {backup_name}")
                        self.backup_transfer_in_progress = False
                        # Signal completion to waiting thread
                        if hasattr(self, 'backup_transfer_complete_event'):
                            self.backup_transfer_complete_event.set()
                            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                            print(f"[{timestamp}] 🎯 DEBUG: backup_transfer_complete_event.set() called")
                        else:
                            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                            print(f"[{timestamp}] [warning] DEBUG: backup_transfer_complete_event not found!")
            else:
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{timestamp}] 💥 BACKUP TRANSFER: Assembly failed for '{backup_name}' from {player_id}")
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{timestamp}] [error] DEBUG: Backup assembly failed - setting event anyway")
                # Signal failure to waiting thread
                if hasattr(self, 'backup_transfer_complete_event'):
                    self.backup_transfer_complete_event.set()
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] 🎯 DEBUG: backup_transfer_complete_event.set() called (failure)")
                else:
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] [warning] DEBUG: backup_transfer_complete_event not found on failure!")

    def _assemble_client_backup(self, player_id: str, backup_name: str) -> bool:
        """Assemble a complete backup from client chunks and extract it."""
        client_key = f"{player_id}:{backup_name}"
        if client_key not in self.client_backup_transfers:
            print(f"[error] BACKUP ASSEMBLY: No transfer data found for '{backup_name}' from {player_id}")
            return False

        transfer = self.client_backup_transfers[client_key]
        print(f"🔧 BACKUP ASSEMBLY: Starting assembly of '{backup_name}' from {player_id} ({transfer['total_chunks']} chunks)")

        try:
            # Assemble the compressed backup data
            backup_data = b''
            for i in range(transfer['total_chunks']):
                if i not in transfer['chunks']:
                    print(f"[error] BACKUP ASSEMBLY: Missing chunk {i} for backup {backup_name}")
                    return False
                backup_data += transfer['chunks'][i]

            print(f"📦 BACKUP ASSEMBLY: Assembled {len(backup_data)} bytes of compressed data for '{backup_name}'")

            # Save to __game_backups directory
            backup_dir = "__game_backups"
            os.makedirs(backup_dir, exist_ok=True)

            # Extract the compressed tar archive
            import tarfile
            import io

            print(f"📂 BACKUP ASSEMBLY: Extracting '{backup_name}' to {backup_dir}/")
            with io.BytesIO(backup_data) as bio:
                with tarfile.open(fileobj=bio, mode='r:gz') as tar:
                    # Extract to backup directory
                    tar.extractall(path=backup_dir)

            print(f"[success] BACKUP ASSEMBLY: Successfully extracted backup '{backup_name}' from {player_id}")

            # Verify backup integrity by checking hash matches name
            extracted_backup_path = os.path.join(backup_dir, backup_name)
            if os.path.exists(extracted_backup_path):
                from coding.non_callable_tools.backup_handling import BackupHandler
                backup_handler = BackupHandler()
                computed_hash = backup_handler.compute_directory_hash(extracted_backup_path, debug=True)
                if computed_hash != backup_name:
                    print(f"[error] BACKUP ASSEMBLY: Hash verification FAILED for '{backup_name}' from {player_id}")
                    print(f"   Expected hash: {backup_name}")
                    print(f"   Computed hash: {computed_hash}")
                    
                    # Clean up corrupted backup
                    import shutil
                    if os.path.isdir(extracted_backup_path):
                        shutil.rmtree(extracted_backup_path)
                    elif os.path.isfile(extracted_backup_path):
                        os.remove(extracted_backup_path)
                    
                    # Send failure acknowledgment
                    error_message = {
                        'type': 'backup_transfer_failed',
                        'backup_name': backup_name,
                        'error': f'Hash verification failed: expected {backup_name}, got {computed_hash}'
                    }
                    self._send_message_to_client(player_id, error_message)
                    print(f"📤 BACKUP ASSEMBLY: Sent hash verification failure acknowledgment to {player_id}")
                    return False
                else:
                    print(f"[success] BACKUP ASSEMBLY: Hash verification PASSED for '{backup_name}' from {player_id}")


            # Clean up transfer data
            del self.client_backup_transfers[client_key]

            # Send success acknowledgment to client
            ack_message = {
                'type': 'backup_transfer_success',
                'backup_name': backup_name
            }
            self._send_message_to_client(player_id, ack_message)
            print(f"📤 BACKUP ASSEMBLY: Sent success acknowledgment to {player_id} for '{backup_name}'")

            return True

        except Exception as e:
            print(f"[error] BACKUP ASSEMBLY: Failed to assemble backup {backup_name} from {player_id}: {e}")

            # Send failure acknowledgment
            error_message = {
                'type': 'backup_transfer_failed',
                'backup_name': backup_name,
                'error': str(e)
            }
            self._send_message_to_client(player_id, error_message)
            print(f"📤 BACKUP ASSEMBLY: Sent failure acknowledgment to {player_id} for '{backup_name}': {e}")

            return False

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
            # Create player's patch directory with proper permissions
            player_patch_dir = os.path.join(self.server_patches_dir, player_id)
            os.makedirs(player_patch_dir, mode=0o755, exist_ok=True)
            
            # Write file
            patch_path = os.path.join(player_patch_dir, f"{patch_name}.json")
            with open(patch_path, 'wb') as f:
                for chunk_num in range(transfer['total']):
                    if chunk_num in transfer['chunks']:
                        f.write(transfer['chunks'][chunk_num])
                    else:
                        raise ValueError(f"Missing chunk {chunk_num}")
            
            print(f"[success] Received complete patch from {player_id}: {patch_name}")
            
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
            print(f"[error] Base backup validation failed: {error}")
            self._notify_patch_merge_failed(f"Incompatible patches: {error}")
            return
        
        print("[success] Base backup validation passed")

        # Step 1.5: Ensure server has required backup
        required_backup = None
        if all_patches_info and all_patches_info[0]:
            required_backup = all_patches_info[0][0].get('base_backup')

        if required_backup:
            available_backups = self._get_available_backups()
            if required_backup not in available_backups:
                print(f"[warning]  Server missing backup '{required_backup}', requesting from client")
                # Find a client that has this backup
                requesting_client = None
                for client_id, backup_name in self.client_backups.items():
                    if backup_name == required_backup:
                        requesting_client = client_id
                        break

                if requesting_client:
                    print(f"🔄 BACKUP TRANSFER: Server missing backup '{required_backup}', requesting from client '{requesting_client}'")

                    # Set up backup transfer tracking
                    self.backup_transfer_in_progress = True
                    self.backup_transfer_client = requesting_client
                    self.backup_transfer_name = required_backup
                    self.backup_transfer_start_time = time.time()
                    self.backup_transfer_complete_event = threading.Event()
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] 🔧 DEBUG: Backup transfer setup - client: {requesting_client}, backup: {required_backup}, event created")

                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] 📨 DEBUG: About to request backup {required_backup} from client {requesting_client}")
                    self._request_backup_from_client(requesting_client, required_backup)
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] 📤 BACKUP TRANSFER: Sent request to {requesting_client} for backup '{required_backup}'")
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] 🎪 DEBUG: backup_transfer_in_progress: {self.backup_transfer_in_progress}, event exists: {hasattr(self, 'backup_transfer_complete_event')}")
                    print(f"⏳ BACKUP TRANSFER: Waiting for backup transfer (30s timeout)...")

                    # Wait for backup transfer to complete with timeout
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] ⏳ DEBUG: Starting to wait for backup transfer event (30s timeout)")
                    if not self.backup_transfer_complete_event.wait(timeout=30.0):
                        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                        print(f"[{timestamp}] [error] BACKUP TRANSFER: TIMEOUT - Backup '{required_backup}' not received within 30 seconds")
                        self._notify_patch_merge_failed(f"Backup transfer timeout for '{required_backup}'")
                        return

                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] [success] DEBUG: Backup transfer event received - proceeding with merge")
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] [success] BACKUP TRANSFER: Successfully received backup '{required_backup}'")
                else:
                    print(f"[error] No client has backup '{required_backup}'")
                    self._notify_patch_merge_failed(f"Required backup '{required_backup}' not available")
                    return

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
        # Ensure output directory exists with proper permissions
        os.makedirs(self.server_patches_dir, mode=0o755, exist_ok=True)
        output_path = os.path.join(self.server_patches_dir, "merged_patch.json")
        success = False
        
        for attempt in range(3):
            print(f"\n--- Merge Attempt {attempt + 1}/3 ---")
            
            # Merge all patches iteratively
            success, result = self._merge_patches_iteratively(all_patch_paths, output_path)
            
            if success:
                print(f"[success] Merge successful on attempt {attempt + 1}")
                break
            else:
                print(f"[warning]  Merge had conflicts: {result}")
                
                # Try to auto-fix conflicts
                print("Running auto_fix_conflicts...")
                try:
                    settings = {}
                    settings_dict = load_settings()
                    if settings_dict.get("success"):
                        settings["selected_provider"] = settings_dict.get("selected_provider", "GEMINI")
                        if settings["selected_provider"] == "GEMINI":
                            settings["api_key"] = settings_dict.get("gemini_api_key", "")
                        elif settings["selected_provider"] == "OPENAI":
                            settings["api_key"] = settings_dict.get("openai_api_key", "")
                        else:
                            print("WARNING: Invalid provider, using default settings")
                            success = False
                            break
                        settings["model_name"] = settings_dict.get("model", "models/gemini-3-flash-preview")
                    else:
                        print("WARNING: No settings found, NO API KEY --> NO AUTO-FIX")
                        success = False
                        break

                    base_backup_name = all_patches_info[0][0].get('base_backup', 'Unknown')
                    auto_fix_conflicts(settings, output_path, patch_paths=all_patch_paths, base_backup=base_backup_name)
                    
                    # Check if conflicts remain
                    remaining_conflicts = get_all_conflicts(output_path)
                    if len(remaining_conflicts) == 0:
                        print("[success] Auto-fix resolved all conflicts!")
                        success = True
                        break
                    else:
                        print(f"[warning]  {len(remaining_conflicts)} conflicts remain after auto-fix")
                except Exception as e:
                    print(f"[error] Auto-fix failed: {e}")
        
        # Step 4: Check final result
        if not success:
            print("\n[error] MERGE FAILED AFTER 3 ATTEMPTS")
            self._notify_patch_merge_failed("Patches are incompatible - could not resolve conflicts after 3 attempts")
            return
        
        print("\n[success] MERGE SUCCESSFUL - Applying to server")

        # Apply merged patch to server's GameFolder
        try:
            vc = VersionControl()
            vc.apply_all_changes(
                needs_rebase=True,
                path_to_BASE_backup="__game_backups",
                file_containing_patches=output_path,
                skip_warnings=True
            )
            self.arena = None  # CRITICAL: Stop game loop from using old objects before reload
            reloaded_setup = reload_game_code() 
            if reloaded_setup:
                # Re-import the setup function since it was imported at startup
                from GameFolder.setup import setup_battle_arena
                print("[success] Server GameFolder modules deep reloaded with merged patches")
            else:
                print("[warning] Server GameFolder reload failed, may use old code")

            self._load_game_files()  # Reload with patched code

            self.arena = None
            print("[success] Server GameFolder updated with merged patches")
        except Exception as e:
            print(f"[error] Failed to apply patches to server: {e}")
            self._notify_patch_merge_failed(f"Server patch application failed: {e}")
            return

        print("Distributing to clients")

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
        
        # Ensure output directory exists with proper permissions
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, mode=0o755, exist_ok=True)
        
        if len(patch_paths) == 1:
            # Only one patch - just copy it
            import shutil
            try:
                shutil.copy(patch_paths[0], output_path)
            except PermissionError as e:
                # Try to fix permissions and retry
                os.makedirs(output_dir, mode=0o755, exist_ok=True)
                # Remove existing file if it exists and is not writable
                if os.path.exists(output_path):
                    try:
                        os.chmod(output_path, 0o644)
                    except:
                        os.remove(output_path)
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
                self._send_data_safe(client_socket, length_bytes + data)
            except Exception as e:
                print(f"Failed to notify {player_id}: {e}")
        
        # Reset state
        self.clients_ready_status.clear()
        self.client_patches.clear()
    
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
        self._restore_gamefolder_to_base()

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
        self._restore_gamefolder_to_base()

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

    def _broadcast_game_state(self):
        """Broadcast the current game state to all clients."""
        if not self.arena or not self.clients:
            return
        
        # Fix #2: Prevent sending state before clients have reloaded their classes
        # Uses issubset to ensure ALL currently connected clients are ready
        if not set(self.clients.keys()).issubset(self.clients_file_sync_ack):
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

        # Check if game just finished
        if self.arena.game_over and not self.waiting_for_restart:
            self.game_finished_time = time.time()
            self.waiting_for_restart = True

            winner_name = self.arena.winner.id if self.arena.winner and hasattr(self.arena.winner, 'id') else "Unknown"
            print(f"\n🎉 GAME OVER! Winner: {winner_name}")
            print(f"🏆 Restarting server in {self.restart_delay} seconds...")

            # Notify all clients about game end and restart
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
                except Exception as e:
                    print(f"Failed to send restart notification to {player_id}: {e}")

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

        # Note: Game over detection and restart messaging is now handled in the game loop



        # Serialize once
        try:
            # Use protocol 4 for better compatibility and to avoid encoding issues
            data = pickle.dumps(game_state, protocol=4)
            length_bytes = len(data).to_bytes(4, byteorder='big')
        except Exception as e:
            print(f"[warning] Failed to serialize game state: {e}")
            # DEBUG: Diagnose class mismatch
            try:
                if self.arena and self.arena.characters:
                    char = self.arena.characters[0]
                    print(f"DEBUG: Character instance class: {char.__class__}")
                    print(f"DEBUG: Character instance class ID: {id(char.__class__)}")
                    import sys
                    if 'GameFolder.characters.GAME_character' in sys.modules:
                         mod = sys.modules['GameFolder.characters.GAME_character']
                         print(f"DEBUG: Sys Module Character class ID: {id(getattr(mod, 'Character', None))}")
                         if id(char.__class__) != id(getattr(mod, 'Character', None)):
                              print("[error] CRITICAL: Class ID Mismatch detected!")
                    else:
                        print("DEBUG: GameFolder.characters.GAME_character not in sys.modules")
            except Exception as debug_e:
                print(f"Error during debug printing: {debug_e}")
            
            # Skip this broadcast frame to prevent server crash
            return

        # Send to all clients
        disconnected_clients = []
        # Create snapshot to avoid RuntimeError if dictionary is modified during iteration
        for player_id, client_socket in list(self.clients.items()):
            try:
                self._send_data_safe(client_socket, length_bytes + data)
            except Exception as e:
                print(f"Failed to send to {player_id}: {e}")
                disconnected_clients.append(player_id)

        # Clean up disconnected clients
        for player_id in disconnected_clients:
            self._handle_client_disconnect(player_id)


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
