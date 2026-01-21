"""
Click handlers for the BaseMenu class.
These methods handle user interactions and menu navigation.
"""

import os
import threading
from BASE_files.BASE_menu_helpers import encrypt_api_key, decrypt_api_key


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

    def on_practice_mode_click(self):
        """Handle practice mode button click."""
        if not self.menu.player_id.strip():
            self.menu.show_error_message("Error: Please enter a Player ID before starting practice mode")
            return
        print("Practice Mode clicked")
        self.menu.network.create_local_room(practice_mode=True)
        self.menu.show_menu("room")

    def on_create_remote_room_click(self):
        """Handle remote public game button click."""
        if not self.menu.player_id.strip():
            self.menu.show_error_message("Error: Please enter a Player ID before creating a room")
            print("Error: Please enter a Player ID before creating a room")
            return
        print("Remote Public Game clicked")
        if self.menu.network.create_remote_room():
            self.menu.show_menu("room")
        else:
            self.menu.show_error_message("Failed to connect to remote server")
            print("Failed to connect to remote server")

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
        from BASE_files.BASE_menu_helpers import decrypt_code
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
        self.menu.show_menu("main")

    def on_library_click(self):
        """Handle library button click."""
        print("Library clicked")
        self.menu.show_menu("library")

    def on_agent_content_click(self):
        """Handle agent content button click."""
        print("Agent Content clicked")
        if not self.menu.ensure_base_workspace():
            self.menu.show_error_message("Failed to restore base workspace; agent may be unsafe.")

        self.menu.show_menu("agent")

    def on_settings_click(self):
        """Handle settings button click."""
        print("Settings clicked")
        self.menu.show_menu("settings")

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
            print(f"Sending patches to server for player: {self.menu.player_id}")
            selected_patches = self.menu.patch_manager.get_selected_patches_info(current_username=self.menu.player_id)

            # Send patches to server
            self.menu.client.send_patches_selection(selected_patches)

            print(f"Sent {len(selected_patches)} patch(es) to server")
        else:
            print("Not connected to server!")

    def on_back_to_menu_click(self):
        """Handle back to menu button click."""
        print("Back to Menu clicked")

        # Clear patch selections when leaving room
        self.menu.patch_manager.clear_selections()
        print("✓ Patch selections cleared")

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
            # Components handle their own focus
            return

        self.menu.agent_running = True
        self.menu.agent_results = None
        self.menu.show_fix_prompt = False

        # Use the active patch as the starting point if one is loaded
        patch_to_load = self.menu.agent_active_patch_path

        # Run agent in a separate thread to avoid blocking the UI
        agent_thread = threading.Thread(
            target=self.menu.run_agent, 
            args=(self.menu.agent_prompt,), 
            kwargs={
                'patch_to_load': patch_to_load,
                'needs_rebase': False # The UI handles rebase during "Load" or initial start
            },
            daemon=True
        )
        agent_thread.start()
        self.menu.agent_thread = agent_thread

    def on_agent_stop_click(self):
        """Handle agent stop button click."""
        print("Agent Stop clicked")
        if self.menu.agent_running:
            self.menu.stop_agent_immediately()

    def on_agent_fix_click(self):
        """Handle agent fix button click."""
        print("Agent Fix clicked")
        self.menu.agent_running = True
        self.menu.show_fix_prompt = False

        # Run agent fix in a separate thread
        agent_thread = threading.Thread(target=self.menu.run_agent_fix, args=(self.menu.agent_results,), daemon=True)
        agent_thread.start()
        self.menu.agent_thread = agent_thread

    def on_agent_save_patch_click(self):
        """Handle agent save patch button click."""
        print(f"Agent Save Patch clicked: {self.menu.patch_name}")

        # Save the current changes as a patch
        patches_dir = "__patches"
        if not os.path.exists(patches_dir):
            os.makedirs(patches_dir)

        # Use current backup name from agent results if available, else from menu base
        backup_name = self.menu.base_working_backup
        if self.menu.agent_values and "backup_name" in self.menu.agent_values:
            backup_name = self.menu.agent_values["backup_name"]

        # Save the patch
        patch_path = os.path.join(patches_dir, f"{self.menu.patch_name}.json")
        success = self.menu.action_logger.save_changes_to_extension_file(patch_path, name_of_backup=backup_name)

        if success:
            print(f"✓ Patch saved successfully: {patch_path}")
            # Clear the patch name field
            self.menu.patch_name = ""
            # Refresh patch list
            self.menu.patch_manager.scan_patches()
        else:
            print("✗ Failed to save patch")

    def on_agent_back_click(self):
        """Handle agent back button click."""
        print("Agent Back clicked")
        # Reset agent state
        self.menu.agent_prompt = ""
        self.menu.agent_running = False
        self.menu.agent_results = None
        # Reset patch state
        self.menu.patch_name = ""
        self.menu.show_fix_prompt = False
        self.menu.agent_selected_patch_idx = -1
        self.menu.agent_active_patch_path = None
        self.menu.show_menu("main")

    def on_load_patch_to_agent_click(self, patch_index: int):
        """Handle loading a patch into the agent for updating."""
        if patch_index < 0 or patch_index >= len(self.menu.patch_manager.available_patches):
            return
        
        patch = self.menu.patch_manager.available_patches[patch_index]
        print(f"Loading patch '{patch.name}' into workspace...")
        
        # We perform the loading in a background thread to keep UI responsive
        def load_task():
            from coding.non_callable_tools.version_control import VersionControl
            vc = VersionControl()
            success, errors = vc.apply_all_changes(
                needs_rebase=True, 
                path_to_BASE_backup="__game_backups", 
                file_containing_patches=patch.file_path,
                skip_warnings=True
            )
            if success:
                self.menu.agent_selected_patch_idx = patch_index
                self.menu.agent_active_patch_path = patch.file_path
                # Update the base working backup to match the patch's base
                backup_name, _, _ = vc.load_from_extension_file(patch.file_path)
                self.menu.base_working_backup = backup_name
                
                # Run tests after loading to check for issues
                print("Running tests on loaded patch...")
                from coding.tools.testing import run_all_tests_tool
                test_results = run_all_tests_tool(explanation="Post-patch-load validation test run")
                
                # Set agent results so fix button can appear if tests failed
                passed = test_results.get('passed_tests', 0)
                total = test_results.get('total_tests', 0)
                self.menu.agent_results = {'passed': passed, 'total': total, 'test_output': test_results}
                
                print(f"✓ Patch '{patch.name}' loaded. Tests: {passed}/{total} passed.")
                if passed < total:
                    print("[warning] Tests failed - Fix button is now available.")
                self.menu.show_error_message(f"Loaded: {patch.name} ({passed}/{total} tests passed)")
            else:
                print(f"✗ Failed to load patch: {errors}")
                self.menu.show_error_message(f"Load failed: {errors}")

        load_thread = threading.Thread(target=load_task)
        load_thread.start()

    def on_reset_to_base_click(self):
        """Reset the workspace back to the base backup."""
        print("Resetting to base backup...")

        def reset_task():
            try:
                from coding.non_callable_tools.backup_handling import BackupHandler
                # Restore the base backup directly
                backup_handler = BackupHandler("__game_backups")
                success, _ = backup_handler.restore_backup(self.menu.base_working_backup, target_path="GameFolder")
                if success is None:
                    print(f"[error] Failed to reset to base backup: {self.menu.base_working_backup}")
                    return False

                if success:
                    # Clear loaded patch state
                    self.menu.agent_selected_patch_idx = -1
                    self.menu.agent_active_patch_path = None
                    print("✓ Successfully reset to base backup")
                    self.menu.show_error_message("Reset to base game")
                else:
                    print("✗ Failed to reset to base backup")
                    self.menu.show_error_message("Reset failed")
            except Exception as e:
                print(f"✗ Error resetting to base: {e}")
                self.menu.show_error_message(f"Reset error: {e}")

        reset_thread = threading.Thread(target=reset_task)
        reset_thread.start()

    def on_settings_save_click(self):
        """Handle settings save button click."""
        print("Settings Save clicked")
        from BASE_files.BASE_menu_helpers import create_settings_file
    
        result = create_settings_file(
            username=self.menu.settings_username,
            gemini_api_key=self.menu.settings_gemini_key,
            openai_api_key=self.menu.settings_openai_key,
            selected_provider=self.menu.selected_provider,
            model_name=self.menu.settings_model,
            base_working_backup=self.menu.base_working_backup,
            already_encrypted=False
        )
        
        if result["success"]:
            print(f"Settings saved: {result['result']}")
            self.menu.show_error_message("Settings saved successfully!")
        else:
            print(f"Failed to save settings: {result['result']}")
            self.menu.show_error_message(f"Failed to save settings: {result['result']}")

    def on_settings_back_click(self):
        """Handle settings back button click."""
        print("Settings Back clicked")
        self.menu.show_menu("main")

    def on_save_current_state_click(self):
        """Handle saving the current GameFolder state to a patch (even if failed)."""
        if not self.menu.patch_name.strip():
            self.menu.show_error_message("Please enter a patch name first")
            # Components handle their own focus
            return

        print(f"Saving current state to patch: {self.menu.patch_name}")

        patches_dir = "__patches"
        if not os.path.exists(patches_dir):
            os.makedirs(patches_dir)

        # Use active backup (from loaded patch) or fallback to base working backup
        backup_name = self.menu.base_working_backup
        if not backup_name:
            # If no backup is set, create a fresh one as the base
            from coding.non_callable_tools.backup_handling import BackupHandler
            handler = BackupHandler("__game_backups")
            _, backup_name = handler.create_backup("GameFolder")
            print(f"Created fresh backup for comparison: {backup_name}")

        patch_path = os.path.join(patches_dir, f"{self.menu.patch_name}.json")
        success = self.menu.action_logger.save_changes_to_extension_file(patch_path, name_of_backup=backup_name)

        if success:
            print(f"✓ State saved successfully: {patch_path}")
            self.menu.patch_name = ""
            # Refresh patch list
            self.menu.patch_manager.scan_patches()
            self.menu.show_error_message(f"Saved: {self.menu.patch_name}")
        else:
            self.menu.show_error_message("Failed to save current state")
