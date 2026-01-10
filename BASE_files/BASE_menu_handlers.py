"""
Click handlers for the BaseMenu class.
These methods handle user interactions and menu navigation.
"""

import os
import threading


class MenuHandlers:
    """Handles user interactions and menu navigation."""

    def __init__(self, menu_instance):
        self.menu = menu_instance

    def on_create_local_room_click(self):
        """Handle create local room button click."""
        if not self.menu.player_id.strip():
            self.menu.show_error_message("Error: Please enter a Player ID before creating a room")
            print("Error: Please enter a Player ID before creating a room")
            return
        print("Create Local Room clicked")
        self.menu.network.create_local_room()
        self.menu.show_menu("room")

    def on_create_remote_room_click(self):
        """Handle create remote room button click."""
        if not self.menu.player_id.strip():
            self.menu.show_error_message("Error: Please enter a Player ID before creating a room")
            print("Error: Please enter a Player ID before creating a room")
            return
        print("Create Remote Room clicked")
        self.menu.network.create_remote_room()
        self.menu.show_menu("room")

    def on_join_room_click(self):
        """Handle join room button click."""
        if not self.menu.player_id.strip():
            self.menu.show_error_message("Error: Please enter a Player ID before joining a room")
            print("Error: Please enter a Player ID before joining a room")
            return
        print("Join Room clicked - entering code entry")
        self.menu.show_menu("join_room_code")

    def on_join_room_with_code_click(self):
        """Handle join room with code button click."""
        if not self.menu.join_room_code.strip():
            self.menu.show_error_message("Please enter a room code")
            return

        # Decrypt the code to get IP and PORT
        from BASE_files.BASE_helpers import decrypt_code
        try:
            server_ip, server_port = decrypt_code(self.menu.join_room_code.strip())
            print(f"Joining room at {server_ip}:{server_port}")

            # Store the target server info and show room menu
            self.menu.target_server_ip = server_ip
            self.menu.target_server_port = server_port
            self.menu.show_menu("room")
        except Exception as e:
            self.menu.show_error_message(f"Invalid room code: {str(e)}")

    def on_join_room_back_click(self):
        """Handle back button from join room code menu."""
        print("Join Room Back clicked")
        self.menu.join_room_code_focused = False
        self.menu.show_menu("main")

    def on_library_click(self):
        """Handle library button click."""
        print("Library clicked")
        self.menu.show_menu("library")

    def on_agent_content_click(self):
        """Handle agent content button click."""
        print("Agent Content clicked")
        self.menu.show_menu("agent")

    def on_settings_click(self):
        """Handle settings button click."""
        print("Settings clicked")
        # TODO: Show settings menu

    def on_quit_click(self):
        """Handle quit button click."""
        print("Quit clicked")
        self.menu.running = False

    def on_ready_click(self):
        """Handle ready button click - sends patches to server."""
        print("Ready clicked - sending patches to server")
        if self.menu.client and self.menu.client.connected:
            # Mark as ready
            self.menu.patches_ready = True

            # Get selected patches info
            selected_patches = self.menu.patch_manager.get_selected_patches_info()

            # Send patches to server
            self.menu.client.send_patches_selection(selected_patches)

            print(f"Sent {len(selected_patches)} patch(es) to server")
        else:
            print("Not connected to server!")

    def on_back_to_menu_click(self):
        """Handle back to menu button click."""
        print("Back to Menu clicked")

        # Disconnect client first
        if self.menu.client and self.menu.client.connected:
            self.menu.client.disconnect()

        # If this client is hosting the server, shut it down when leaving
        if self.menu.network.server_instance and self.menu.network.server_thread and self.menu.network.server_thread.is_alive():
            print("Shutting down server (you were the host)...")
            # Stop the server cleanly
            self.menu.network.server_instance.stop()
            # Wait for server thread to finish
            self.menu.network.server_thread.join(timeout=2.0)
            self.menu.network.server_instance = None
            self.menu.network.server_thread = None

        self.menu.show_menu("main")

    def on_library_back_click(self):
        """Handle library back button click."""
        print("Library Back clicked")
        self.menu.show_menu("main")

    def on_agent_send_click(self):
        """Handle agent send button click."""
        print("Agent Send clicked")

        # Focus the text field if prompt is empty
        if not self.menu.agent_prompt.strip():
            self.menu.agent_prompt_focused = True
            return

        self.menu.agent_running = True
        self.menu.agent_results = None
        self.menu.show_fix_prompt = False
        # Unfocus text fields
        self.menu.agent_prompt_focused = False
        self.menu.patch_name_focused = False

        # Run agent in a separate thread to avoid blocking the UI
        agent_thread = threading.Thread(target=self.menu.run_agent, args=(self.menu.agent_prompt,))
        agent_thread.start()

    def on_agent_fix_click(self):
        """Handle agent fix button click."""
        print("Agent Fix clicked")
        self.menu.agent_running = True
        self.menu.show_fix_prompt = False
        # Unfocus text fields
        self.menu.agent_prompt_focused = False
        self.menu.patch_name_focused = False

        # Run agent fix in a separate thread
        agent_thread = threading.Thread(target=self.menu.run_agent_fix, args=(self.menu.agent_results,))
        agent_thread.start()

    def on_agent_save_patch_click(self):
        """Handle agent save patch button click."""
        print(f"Agent Save Patch clicked: {self.menu.patch_name}")

        # Save the current changes as a patch
        patches_dir = "__patches"
        if not os.path.exists(patches_dir):
            os.makedirs(patches_dir)

        # Get the backup name from agent values, fallback to "GameFolder"
        backup_name = "GameFolder"
        if self.menu.agent_values and "backup_name" in self.menu.agent_values:
            backup_name = self.menu.agent_values["backup_name"]

        # Save the patch
        patch_path = os.path.join(patches_dir, f"{self.menu.patch_name}.json")
        success = self.menu.action_logger.save_changes_to_extension_file(patch_path, name_of_backup=backup_name)

        if success:
            print(f"✓ Patch saved successfully: {patch_path}")
            # Clear the patch name field
            self.menu.patch_name = ""
            self.menu.patch_name_focused = False
        else:
            print("✗ Failed to save patch")

    def on_agent_back_click(self):
        """Handle agent back button click."""
        print("Agent Back clicked")
        # Reset agent state
        self.menu.agent_prompt = ""
        self.menu.agent_prompt_focused = False
        self.menu.agent_running = False
        self.menu.agent_results = None
        # Reset patch state
        self.menu.patch_name = ""
        self.menu.patch_name_focused = False
        self.menu.text_handler.patch_cursor_pos = 0
        self.menu.text_handler.patch_selection_start = 0
        self.menu.text_handler.patch_selection_end = 0
        self.menu.text_handler.patch_scroll_offset = 0
        self.menu.show_fix_prompt = False
        self.menu.text_handler.agent_cursor_pos = 0
        self.menu.text_handler.agent_selection_start = 0
        self.menu.text_handler.agent_selection_end = 0
        self.menu.text_handler.agent_scroll_offset = 0
        self.menu.show_menu("main")
