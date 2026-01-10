"""
Network management methods for the BaseMenu class.
Handles server creation, client connections, and room management.
"""

import threading

from server import GameServer
from BASE_files.BASE_helpers import encrypt_code
from BASE_files.network_client import NetworkClient
from BASE_files.BASE_helpers import REMOTE_DOMAIN


class MenuNetwork:
    """Handles network operations for the menu system."""

    def __init__(self, menu_instance):
        self.menu = menu_instance
        self.client = None
        self.server_thread = None
        self.server_instance = None
        self.server_host = "127.0.0.1"
        self.server_port = 5555

    def run_server(self, host: str = "127.0.0.1", port: int = 5555):
        """Start the game server."""
        self.server_instance = GameServer(host, port)

        # Start server in a thread
        self.server_thread = threading.Thread(target=self.server_instance.start)
        self.server_thread.start()

    def connect_to_server(self, server_host: str = "127.0.0.1", server_port: int = 5555):
        """Connect to the server, creating client if needed or reconnecting if disconnected."""
        # Store connection info in menu for reconnection
        self.menu.target_server_ip = server_host
        self.menu.target_server_port = server_port

        if not self.client:
            self.client = NetworkClient(server_host, server_port)
        else:
            # Update host and port in case they changed
            self.client.host = server_host
            self.client.port = server_port

        # Only connect if not already connected
        self.client.disconnect()
        print(f"Attempting to connect to server at {server_host}:{server_port}...")
        if not self.client.connect(self.menu.player_id):
            print("Failed to connect to server!")
            return False

        # Set up callbacks (do this every time in case they were reset)
        self.client.on_file_received = self.menu.file_received_callback
        self.client.on_file_transfer_progress = self.menu.file_transfer_progress_callback
        self.client.on_name_rejected = self.menu.name_rejected_callback
        self.client.on_game_start = self.menu.game_start_callback
        self.client.on_patch_received = self.menu.patch_received_callback
        self.client.on_patch_sync_failed = self.menu.patch_sync_failed_callback
        self.client.on_patch_merge_failed = self.menu.patch_merge_failed_callback
        self.client.on_game_restarting = self.menu.game_restarting_callback
        self.client.on_server_restarted = self.menu.server_restarted_callback
        self.client.on_disconnected = self.menu.disconnected_callback

        return True

    def create_local_room(self):
        """Create a local room (accessible on the local network)."""
        print("Creating local room...")
        # Get the actual local IP for room code generation
        from BASE_files.BASE_helpers import get_local_ip
        local_ip = get_local_ip()
        # Generate a room code using the actual local IP
        self.menu.room_code = encrypt_code(local_ip, self.server_port, "LOCAL")
        print(f"Local room code: {self.menu.room_code}")
        # Bind to all interfaces (0.0.0.0) so other machines can connect
        self.run_server("0.0.0.0", self.server_port)
        self.connect_to_server("localhost", self.server_port)

    def create_remote_room(self):
        """Create a remote room (accessible from other machines)."""
        print("Creating remote room...")
        # For remote rooms, we need to get the external IP
        # TODO: Implement actual external IP detection (e.g., using services like ipify.org)
        # For now, we'll use 127.0.0.1 as placeholder - user should replace with actual external IP
        #self.run_server("0.0.0.0", self.server_port)  # Listen on all interfaces

        # Generate room code using the external IP
        self.menu.room_code = encrypt_code(REMOTE_DOMAIN, self.server_port, "REMOTE")
        print(f"Room code generated: {self.menu.room_code}")
        print("NOTE: For remote rooms to work, replace the external_ip with your actual external IP address")

        # Connect to the remote server
        if not self.connect_to_server(REMOTE_DOMAIN, self.server_port):
            print("Failed to connect to remote server!")
            return False
        return True
