import os

# Set video driver BEFORE importing pygame
os.environ['SDL_VIDEODRIVER'] = 'cocoa'

import pygame
import importlib
import time
import sys
import traceback
import platform
import subprocess
import threading

from BASE_files.network_client import NetworkClient, EntityManager, sync_game_files
from BASE_files.patch_manager import PatchManager
from BASE_files.BASE_game_client import run_client
from BASE_files.BASE_helpers import encrypt_code, decrypt_code, decrypt_api_key
from BASE_files.BASE_menu_renderers import MenuRenderers
from BASE_files.BASE_menu_handlers import MenuHandlers
from BASE_files.BASE_menu_network import MenuNetwork
from coding.non_callable_tools.version_control import VersionControl
from coding.non_callable_tools.action_logger import ActionLogger

# Features:
# - Main menu
# -- Create/Join room
# - Library
# -- View/Download/Install/Update games
# - Room
# -- You are in a room and you sync asking the server for the game files
# -- You can vote to start the game


class BaseMenu:
    def __init__(self, action_logger=None):
        print("Initializing BaseMenu...")
        # Initialize pygame if not already initialized
        if not pygame.get_init():
            pygame.init()
            # Enable key repeat for continuous input (delay=300ms, interval=35ms)
            pygame.key.set_repeat(300, 35)
            print("Pygame initialized by BaseMenu.")

        # Initialize clipboard support
        try:
            if hasattr(pygame.scrap, 'init'):
                pygame.scrap.init()
            print("Clipboard support initialized.")
        except:
            print("Warning: Clipboard support not available.")

        print("Creating window...")
        self.screen = pygame.display.set_mode((1400, 900))

        print(f"Video Driver: {pygame.display.get_driver()}")

        pygame.display.set_caption("GenGame - Multiplayer Menu")
        print("Window created successfully.")
        self.clock = pygame.time.Clock()
        self.running = True

        # Menu state
        self.current_menu = "main"  # main, join_room_code, library, room, agent

        # Error message display
        self.error_message = None
        self.error_message_time = 0

        print("Loading fonts...")
        try:
            self.menu_font = pygame.font.Font(None, 48)  # Title font
            self.button_font = pygame.font.Font(None, 32)  # Button font
            self.small_font = pygame.font.Font(None, 24)   # Small text font
            print("Fonts loaded successfully.")
        except Exception as e:
            print(f"Warning: Could not load default font: {e}. Trying SysFont...")
            self.menu_font = pygame.font.SysFont("Arial", 48)
            self.button_font = pygame.font.SysFont("Arial", 32)
            self.small_font = pygame.font.SysFont("Arial", 24)

        # Game state
        self.player_id = ""
        self.in_room = False
        self.room_code = ""  # Code displayed when creating a room
        self.join_room_code = ""  # Code entered when joining a room
        self.available_games = []
        self.patch_to_apply = None

        # Agent menu state
        self.agent_prompt = ""
        self.agent_running = False
        self.agent_results = None
        self.show_fix_prompt = False
        self.agent_values = None
        self.agent_selected_patch_idx = -1  # Index of patch selected for loading
        self.agent_active_patch_path = None # Path to the currently loaded patch

        # Patch saving state
        self.patch_name = ""

        # Patch manager
        self.patch_manager = PatchManager()
        self.patch_manager.scan_patches()  # Initial scan
        self.patches_ready = False  # Track if player marked patches as ready

        # Initialize component classes
        self.network = MenuNetwork(self)
        self.handlers = MenuHandlers(self)
        self.renderers = MenuRenderers(self)

        # Action logger for patch saving - use provided instance or create new one
        self.action_logger = action_logger if action_logger is not None else ActionLogger()

        # Settings state
        self.settings_username = ""
        self.settings_gemini_key = ""
        self.settings_openai_key = ""
        self.settings_model = "models/gemini-3-flash-preview"
        self.selected_provider = "GEMINI"
        self.base_working_backup = None

        # Game menu
        self.on_start() # includes loading settings

        print("BaseMenu initialization complete.")

    def show_menu(self, menu_name: str):
        """Switch to a different menu."""
        self.current_menu = menu_name

        # Set room state
        if menu_name == "room":
            self.in_room = True
            # Reset PatchBrowser cache when entering room to ensure clean state
            room_ui = self.renderers.managers.get("room")
            if room_ui:
                for comp in room_ui.components:
                    if hasattr(comp, 'reset_cache'):
                        comp.reset_cache()
        else:
            self.in_room = False

        # Scan patches when entering menus that use them
        if menu_name in ["room", "library", "agent"]:
            self.patch_manager.scan_patches()

    def render(self):
        """Render the current menu."""
        self.renderers.render()

        pygame.display.flip()

    def run_menu_loop(self):
        """Main menu loop."""
        print("Starting menu loop...")
        while self.running:
            self.clock.tick(60)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    print("Quit event received.")
                    self.running = False
                else:
                    # Delegate events to the UI manager first
                    ui = self.renderers._get_current_ui()
                    if ui and ui.handle_event(event):
                        continue

                    # Fallback for events not consumed by UI
                    if event.type == pygame.KEYDOWN:
                        self.handle_key_input(event)

            # Update network client if connected
            if self.client:
                self.client.update()

            # Only render if still running (in case game was started during update)
            if self.running:
                self.render()

        print("Menu loop finished.")
        pygame.quit()

    def handle_key_input(self, event):
        """Handle keyboard input by delegating to current UI manager."""
        ui = self.renderers._get_current_ui()
        if ui and ui.handle_event(event):
            return

        # Global keys
        if event.key == pygame.K_ESCAPE:
            if self.current_menu != "main":
                self.handlers.on_back_to_menu_click()

    # Delegate all click handlers to the handlers module
    def on_create_local_room_click(self):
        self.handlers.on_create_local_room_click()

    def on_create_remote_room_click(self):
        self.handlers.on_create_remote_room_click()

    def on_join_room_click(self):
        self.handlers.on_join_room_click()

    def on_join_room_with_code_click(self):
        self.handlers.on_join_room_with_code_click()

    def on_join_room_back_click(self):
        self.handlers.on_join_room_back_click()

    def on_library_click(self):
        self.handlers.on_library_click()

    def on_agent_content_click(self):
        self.handlers.on_agent_content_click()

    def on_settings_click(self):
        self.handlers.on_settings_click()

    def on_settings_save_click(self):
        self.handlers.on_settings_save_click()

    def on_settings_back_click(self):
        self.handlers.on_settings_back_click()

    def on_quit_click(self):
        self.handlers.on_quit_click()

    def on_ready_click(self):
        self.handlers.on_ready_click()
    
    def on_back_to_menu_click(self):
        self.handlers.on_back_to_menu_click()

    def on_library_back_click(self):
        self.handlers.on_library_back_click()

    def on_agent_send_click(self):
        self.handlers.on_agent_send_click()

    def on_agent_fix_click(self):
        self.handlers.on_agent_fix_click()

    def on_agent_save_patch_click(self):
        self.handlers.on_agent_save_patch_click()

    def on_agent_back_click(self):
        self.handlers.on_agent_back_click()

    # Delegate network operations to network module
    @property
    def client(self):
        return self.network.client

    @property
    def server_thread(self):
        return self.network.server_thread

    @property
    def server_instance(self):
        return self.network.server_instance

    @property
    def server_host(self):
        return self.network.server_host

    @property
    def server_port(self):
        return self.network.server_port

    # Clipboard functionality
    def paste_clipboard(self):
        """Get clipboard content and return it as a string."""
        system = platform.system().lower()
        clipboard_text = ""

        # Try platform-specific clipboard first
        try:
            if system == "darwin":  # macOS
                result = subprocess.run(['pbpaste'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout:
                    clipboard_text = result.stdout
            elif system == "linux":
                # Try xclip first, then xsel
                for cmd in [['xclip', '-selection', 'clipboard', '-o'], ['xsel', '--clipboard', '--output']]:
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                        if result.returncode == 0 and result.stdout:
                            clipboard_text = result.stdout
                            break
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        continue
            elif system == "windows":
                result = subprocess.run(['powershell', 'Get-Clipboard'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout:
                    clipboard_text = result.stdout
        except Exception as e:
            print(f"Platform clipboard failed: {e}")

        # Fallback to pygame.scrap
        if not clipboard_text:
            try:
                if hasattr(pygame.scrap, 'get_init') and not pygame.scrap.get_init():
                    pygame.scrap.init()
                clip = pygame.scrap.get(pygame.SCRAP_TEXT)
                if clip:
                    clipboard_text = clip.decode('utf-8')
            except Exception:
                pass

        if clipboard_text:
            # Normalize line endings and remove null bytes
            clipboard_text = clipboard_text.replace('\x00', '').replace('\r\n', '\n').replace('\r', '\n')
            print(f"Clipboard content retrieved: {len(clipboard_text)} characters")
            
            # If we're in the agent menu, update the prompt field directly for backward compatibility
            # or better yet, the component should call this and handle the return value.
            return clipboard_text
        
        print("Failed to retrieve clipboard content")
        return ""

    # Agent functionality
    def run_agent(self, prompt: str, patch_to_load: str = None, needs_rebase: bool = True):
        """Run the agent with the given prompt."""
        try:
            from agent import new_main
            success, modelHandler, todo_list, prompt, backup_name = new_main(
                prompt=prompt,
                start_from_base=self.base_working_backup,
                patch_to_load=patch_to_load,
                needs_rebase=needs_rebase,
                UI_called=True,
                provider=self.selected_provider,
                model_name=self.settings_model,
                gemini_api_key=self.settings_gemini_key if self.settings_gemini_key else None,
                openai_api_key=self.settings_openai_key if self.settings_openai_key else None
            )
            self.agent_values = {"success": success, "modelHandler": modelHandler, "todo_list": todo_list, "prompt": prompt, "backup_name": backup_name}
            # Get test results
            from coding.tools.testing import run_all_tests_tool
            test_results = run_all_tests_tool()

            # Use dictionary properties directly
            passed = test_results.get('passed_tests', 0)
            total = test_results.get('total_tests', 0)

            self.agent_results = {'passed': passed, 'total': total, 'test_output': test_results}

        except Exception as e:
            print(f"Error running agent: {e}")
            self.agent_results = {'passed': 0, 'total': 0, 'error': str(e)}
        finally:
            self.agent_running = False

    def run_agent_fix(self, results):
        """Run the agent in fix mode."""
        try:                        
            from agent import full_loop
            
            # Ensure we are working with the raw test results dictionary
            raw_results = results.get('test_output', results) if results else None
            
            if self.agent_values is None:
                # Initialize session for fixing a loaded patch
                print("Creating new agent session for patch fixing...")
                from coding.generic_implementation import GenericHandler
                from coding.non_callable_tools.todo_list import TodoList
                
                selected_api_key = None
                if self.selected_provider == "GEMINI" and self.settings_gemini_key:
                    selected_api_key = self.settings_gemini_key
                elif self.selected_provider == "OPENAI" and self.settings_openai_key:
                    selected_api_key = self.settings_openai_key
                
                modelHandler = GenericHandler(
                    thinking_model=True, 
                    provider=self.selected_provider, 
                    model_name=self.settings_model, 
                    api_key=selected_api_key
                )
                
                todo_list = TodoList()
                backup_name = self.base_working_backup
                
                # Pre-parse results for the starting prompt
                from coding.tools.testing import parse_test_results
                issues_to_fix = parse_test_results(raw_results)
                prompt = (
                    f"## The following tests failed, understand why and fix the issues\n"
                    f"{issues_to_fix}\n"
                )
                
                self.agent_values = {
                    "success": False,
                    "modelHandler": modelHandler,
                    "todo_list": todo_list,
                    "prompt": prompt,
                    "backup_name": backup_name
                }

                # Start visual logging session for the agent session
                self.action_logger.start_session(visual=True)

            
            # Extract state for the fix call
            modelHandler = self.agent_values["modelHandler"] 
            todo_list = self.agent_values["todo_list"]
            prompt = self.agent_values["prompt"]
            backup_name = self.agent_values.get("backup_name", "GameFolder")

            # Call loop with raw results
            success, modelHandler, todo_list, prompt, backup_name = full_loop(
                prompt=prompt, 
                modelHandler=modelHandler, 
                todo_list=todo_list, 
                fix_mode=True, 
                backup_name=backup_name, 
                total_cleanup=False, 
                results=raw_results, 
                UI_called=True
            )
            
            # Update state with results from the fix session
            if success:
                self.agent_values = None
            else:
                self.agent_values = {"success": success, "modelHandler": modelHandler, "todo_list": todo_list, "prompt": prompt, "backup_name": backup_name}

            # Update UI with new test results
            from coding.tools.testing import run_all_tests_tool
            test_results = run_all_tests_tool()
            passed = test_results.get('passed_tests', 0)
            total = test_results.get('total_tests', 0)
            self.agent_results = {'passed': passed, 'total': total, 'test_output': test_results}

        except Exception as e:
            import traceback
            print(f"Error running agent fix: {e}")
            traceback.print_exc()
            self.agent_results = {'passed': 0, 'total': 0, 'error': str(e)}
        finally:
            # End the visual logging session
            self.action_logger.end_session()
            self.agent_running = False

    # Callback methods (used by network client)
    def file_received_callback(self, file_path: str, success: bool):
        """Callback when a file transfer is complete."""
        if success:
            print(f"✓ File received successfully: {file_path}")

            import shutil
            import os
            new_path = os.path.join(os.path.dirname(__file__), "GameFolder", file_path.split("/")[-1])
            shutil.move(file_path, new_path)

            self.patch_to_apply = new_path
        else:
            print(f"✗ Failed to receive file: {file_path}")

    def name_rejected_callback(self, reason: str):
        """Callback when player name is rejected by server."""
        print(f"⚠️  Name rejected: {reason}")
        self.show_error_message(f"Name rejected: {reason}")
        # Disconnect and return to main menu
        if self.client:
            self.client.disconnect()
        self.show_menu("main")

    def patch_received_callback(self, patch_path: str):
        """Callback when patch file is received from server."""
        print(f"📦 Received merge patch: {patch_path}")
        print("🔧 Applying patch to GameFolder...")
        
        # Run patch application in a separate thread to avoid blocking network updates
        patch_thread = threading.Thread(target=self._apply_patch_async, args=(patch_path,), daemon=True)
        patch_thread.start()

    def _apply_patch_async(self, patch_path: str):
        """Apply patch asynchronously to avoid blocking the network loop."""
        # CRITICAL FIX: Ensure we're applying patches from the project root directory
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        original_cwd = os.getcwd()

        # Change to project root to ensure patches are applied correctly
        if os.getcwd() != project_root:
            os.chdir(project_root)

        try:
            # Import version control system to apply the patch
            version_control = VersionControl(self.action_logger, path_to_security_backup="__TEMP_SECURITY_BACKUP")
            result, errors = version_control.apply_all_changes(needs_rebase=True, path_to_BASE_backup="__game_backups", file_containing_patches=patch_path, skip_warnings=True)

            print("\n" * 10)
            if result:
                print("-----    SUCCESS    -----")
                print("All changes applied successfully")
                self.client.send_patch_applied(success=True)
            else:
                print("-----    FAILED    -----")
                print("Some changes failed to apply")
                print(errors)
                error_msg = str(errors) if errors else "Unknown error applying patches"
                self.client.send_patch_applied(success=False, error_message=error_msg)
        except Exception as e:
            print(f"Error applying patch: {e}")
            traceback.print_exc()
            self.client.send_patch_applied(success=False, error_message=str(e))
        finally:
            # Always restore original working directory
            if os.getcwd() != original_cwd:
                os.chdir(original_cwd)

    def patch_sync_failed_callback(self, reason: str, failed_clients: list, details: list):
        """Callback when patch synchronization fails on one or more clients."""
        print(f"❌ Game start aborted: {reason}")
        error_msg = f"Game cannot start - Patch failed on: {', '.join(failed_clients)}"
        self.show_error_message(error_msg)
    
    def patch_merge_failed_callback(self, reason: str):
        """Callback when server-side patch merge fails."""
        print(f"❌ Patch merge failed: {reason}")
        self.show_error_message(f"Patches incompatible: {reason}")
        self.patches_ready = False  # Reset ready status

    def game_start_callback(self):
        """Callback when server notifies us to start the game."""
        print("🎮 Starting game now!")
        self.start_game()

    def show_error_message(self, message: str):
        """Show an error message on screen."""
        self.error_message = message
        self.error_message_time = pygame.time.get_ticks()

    def file_transfer_progress_callback(self,file_path: str, progress: float, direction: str):
        """Callback for file transfer progress updates."""
        print(f"File transfer progress: {direction} {file_path}: {progress*100:.1f}%")

    def game_restarting_callback(self, winner: str, restart_delay: float, message: str):
        """Callback when the server announces game is restarting."""
        print(f"🎉 Game finished! Winner: {winner}")
        print(f"⏳ Server will restart in {restart_delay} seconds...")

        # Clear patch selections for fresh start
        self.patch_manager.clear_selections()
        print("✓ Patch selections cleared for next game")

        self.show_error_message(f"Game Over! Winner: {winner}\nServer restarting in {restart_delay} seconds...")

    def reset_room_state(self):
        """Reset all room-related states to initial values."""
        self.patches_ready = False
        self.in_room = False
        self.room_code = ""
        self.scroll_offset = 0

        # Reset connection attempt time
        if hasattr(self, 'connection_attempt_time'):
            delattr(self, 'connection_attempt_time')

    def reset_ui_states(self):
        """Reset all UI states to prevent button states from getting stuck."""
        # Reset room UI states
        self.patches_ready = False
        self.patch_manager.clear_selections()  # Clear patch selections

        # Reset PatchBrowser cache to force visual refresh
        room_ui = self.renderers.managers.get("room")
        if room_ui:
            for comp in room_ui.components:
                if hasattr(comp, 'reset_cache'):
                    comp.reset_cache()

        # Reset agent menu states
        self.agent_running = False
        self.agent_results = None
        self.show_fix_prompt = False
        self.agent_values = None
        self.agent_selected_patch_idx = -1

        # Reset error message state
        self.error_message = None
        self.error_message_time = 0

    def server_restarted_callback(self, message: str):
        """Callback when the server has restarted and is ready for new games."""
        print(f"🔄 {message}")
        print("Returning to room lobby...")

        # Reset room state and all UI states to clean slate
        self.reset_room_state()
        self.reset_ui_states()

        # Reconnect to the server if we were previously connected
        if hasattr(self, 'target_server_ip') and hasattr(self, 'target_server_port'):
            print(f"Reconnecting to server at {self.target_server_ip}:{self.target_server_port}...")
            if not self.network.connect_to_server(self.target_server_ip, self.target_server_port):
                self.show_error_message("Failed to reconnect to server")
                print("Failed to reconnect to server")

        # Always go to room state when server restarts
        self.show_menu("room")
        self.show_error_message("Server restarted. Ready for new game!")

    def disconnected_callback(self):
        """Callback when client gets disconnected from server."""
        print("🔌 Disconnected from server")
        print("Returning to room menu...")

        # Reset room state since connection is lost
        self.reset_room_state()

        # Go back to room menu and show disconnection message
        self.show_menu("room")
        self.show_error_message("Disconnected from server. Please reconnect.")

    def _load_settings(self):
        """Load settings from config file."""
        import json
        import os

        config_path = os.path.join("__config", "settings.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    settings = json.load(f)
                self.settings_username = settings.get("username", "")
                self.settings_gemini_key = decrypt_api_key(settings.get("gemini_api_key", ""))
                self.settings_openai_key = decrypt_api_key(settings.get("openai_api_key", ""))
                self.selected_provider = settings.get("selected_provider", "GEMINI")
                self.settings_model = settings.get("model", "models/gemini-3-flash-preview")
                self.base_working_backup = settings.get("base_working_backup", None)
                
                # Set player_id to username from settings if available
                if self.settings_username:
                    self.player_id = self.settings_username

                print("Settings loaded successfully")
            except Exception as e:
                print(f"Failed to load settings: {e}")

    def on_start(self):
        self._load_settings()
        from coding.non_callable_tools.helpers import cleanup_old_logs
        cleanup_old_logs()
        self.patch_to_apply = None

        from coding.non_callable_tools.backup_handling import BackupHandler
        handler = BackupHandler("__game_backups")

        # Ensure we have an initial base backup if none is set
        if self.base_working_backup is None:
            print("Creating initial safety backup...")
            try:
                _, self.base_working_backup = handler.create_backup("GameFolder")
                print(f"Initial backup created: {self.base_working_backup}")
                self.handlers.on_settings_save_click()

            except Exception as e:
                print(f"Warning: Failed to create initial backup: {e}")
        else:
            print(f"Restoring from backup: {self.base_working_backup}")
            _, self.base_working_backup = handler.restore_backup(self.base_working_backup, target_path="GameFolder")
            print(f"Backup restored: {self.base_working_backup}")
    
    def start_game(self):
        """Start the game."""
        print("🚀 Launching game client...")
        # File sync should have already happened, patches applied

        # Start the game client - it will run until it exits
        try:
            run_client(network_client=self.client, player_id=self.player_id)
            print("Game client exited normally")
        except SystemExit as e:
            print(f"Game client exited with SystemExit: {e}")
        except Exception as e:
            print(f"Game client exited with error: {e}")

        # Game client exited - return to room menu
        print("🔄 Game client exited, returning to room...")

        # Reset UI states to prevent button states from getting stuck
        self.reset_ui_states()

        self.show_menu("room")
        self.show_error_message("Ready for new game!")


if __name__ == "__main__":
    # Test the menu system
    menu = BaseMenu()
    menu.run_menu_loop()
