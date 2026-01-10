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

from BASE_files.network_client import NetworkClient, EntityManager, sync_game_files
from BASE_files.patch_manager import PatchManager
from BASE_files.BASE_game_client import run_client
from BASE_files.BASE_menu_utils import MenuUtils, TextInputHandler
from BASE_files.BASE_helpers import encrypt_code, decrypt_code
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
        self.base_working_backup = "20260110145521_GameFolder" # Will be initialized in on_start or when loading patches

        print("Initializing BaseMenu...")
        # Initialize pygame if not already initialized
        if not pygame.get_init():
            pygame.init()
            print("Pygame initialized by BaseMenu.")

        # Initialize clipboard support
        try:
            if hasattr(pygame.scrap, 'init'):
                pygame.scrap.init()
            print("Clipboard support initialized.")
        except:
            print("Warning: Clipboard support not available.")

        # Game menu
        self.on_start()

        print("Creating window...")
        self.screen = pygame.display.set_mode((1400, 900))

        print(f"Video Driver: {pygame.display.get_driver()}")

        pygame.display.set_caption("GenGame - Multiplayer Menu")
        print("Window created successfully.")
        self.clock = pygame.time.Clock()
        self.running = True

        # Menu state
        self.current_menu = "main"  # main, join_room_code, library, room, agent
        self.menu_background_color = (20, 20, 30)
        self.menu_text_color = (255, 255, 255)

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

        # Initialize utility classes
        self.utils = MenuUtils(self.screen, self.menu_font, self.button_font, self.small_font,
                              (70, 70, 100), (100, 100, 130), (255, 255, 255))
        self.text_handler = TextInputHandler()

        # Mouse state
        self.mouse_pos = (0, 0)
        self.mouse_clicked = False
        self.frame_count = 0

        # Game state
        self.player_id = ""
        self.player_id_focused = False
        self.in_room = False
        self.room_code = ""  # Code displayed when creating a room
        self.join_room_code = ""  # Code entered when joining a room
        self.join_room_code_focused = False
        self.available_games = []
        self.patch_to_apply = None

        # Agent menu state
        self.agent_prompt = ""
        self.agent_prompt_focused = False
        self.agent_running = False
        self.agent_results = None
        self.show_fix_prompt = False
        self.agent_values = None
        self.agent_selected_patch_idx = -1  # Index of patch selected for loading
        self.agent_active_patch_path = None # Path to the currently loaded patch
        self.agent_scroll_offset = 0        # Scroll offset for patch list in agent menu

        # Patch saving state
        self.patch_name = ""
        self.patch_name_focused = False

        # Patch manager
        self.patch_manager = PatchManager()
        self.patches_ready = False  # Track if player marked patches as ready
        self.scroll_offset = 0  # For scrollable patch list
        self.max_visible_patches = 8  # Number of patches visible at once

        # Initialize component classes
        self.network = MenuNetwork(self)
        self.renderers = MenuRenderers(self)
        self.handlers = MenuHandlers(self)

        # Action logger for patch saving - use provided instance or create new one
        self.action_logger = action_logger if action_logger is not None else ActionLogger()

        print("BaseMenu initialization complete.")

    def show_menu(self, menu_name: str):
        """Switch to a different menu."""
        self.current_menu = menu_name

    def render(self):
        """Render the current menu."""
        self.frame_count += 1

        if self.current_menu == "main":
            self.renderers.render_main_menu()
        elif self.current_menu == "join_room_code":
            self.renderers.render_join_room_code_menu()
        elif self.current_menu == "room":
            self.renderers.render_room_menu()
        elif self.current_menu == "library":
            self.renderers.render_library_menu()
        elif self.current_menu == "agent":
            self.renderers.render_agent_menu()

        pygame.display.flip()

    def run_menu_loop(self):
        """Main menu loop."""
        print("Starting menu loop...")
        while self.running:
            self.clock.tick(60)

            # Reset mouse click state
            self.mouse_clicked = False

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    print("Quit event received.")
                    self.running = False
                elif event.type == pygame.MOUSEMOTION:
                    self.mouse_pos = event.pos
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Left click
                        self.mouse_clicked = True
                elif event.type == pygame.KEYDOWN:
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
        """Handle keyboard input for text fields and scrolling."""
        if self.player_id_focused:
            if event.key == pygame.K_RETURN:
                self.player_id_focused = False
            elif event.key == pygame.K_BACKSPACE:
                self.player_id = self.player_id[:-1]
            elif event.key == pygame.K_ESCAPE:
                self.player_id_focused = False
            else:
                # Add printable characters
                if event.unicode.isprintable():
                    self.player_id += event.unicode

        # Handle join room code input
        elif self.current_menu == "join_room_code" and self.join_room_code_focused:
            if event.key == pygame.K_RETURN:
                self.join_room_code_focused = False
                if self.join_room_code.strip():
                    self.handlers.on_join_room_with_code_click()
            elif event.key == pygame.K_BACKSPACE:
                self.join_room_code = self.join_room_code[:-1]
            elif event.key == pygame.K_ESCAPE:
                self.join_room_code_focused = False
            else:
                # Add printable characters
                if event.unicode.isprintable():
                    self.join_room_code += event.unicode

        # Handle agent prompt input
        elif self.current_menu == "agent" and self.agent_prompt_focused and not self.agent_running:
            mods = pygame.key.get_mods()

            if event.key == pygame.K_RETURN:
                # Insert newline with Enter
                self.agent_prompt = self.text_handler.insert_text(self.agent_prompt, '\n')
            elif event.key == pygame.K_BACKSPACE:
                if self.text_handler.has_selection():
                    self.agent_prompt = self.text_handler.delete_selection(self.agent_prompt)
                elif self.text_handler.agent_cursor_pos > 0:
                    # Delete character before cursor
                    self.agent_prompt = self.agent_prompt[:self.text_handler.agent_cursor_pos-1] + self.agent_prompt[self.text_handler.agent_cursor_pos:]
                    self.text_handler.agent_cursor_pos -= 1
                    self.text_handler.agent_selection_start = self.text_handler.agent_cursor_pos
                    self.text_handler.agent_selection_end = self.text_handler.agent_cursor_pos
            elif event.key == pygame.K_DELETE:
                if self.text_handler.has_selection():
                    self.agent_prompt = self.text_handler.delete_selection(self.agent_prompt)
                elif self.text_handler.agent_cursor_pos < len(self.agent_prompt):
                    # Delete character after cursor
                    self.agent_prompt = self.agent_prompt[:self.text_handler.agent_cursor_pos] + self.agent_prompt[self.text_handler.agent_cursor_pos+1:]
            elif event.key == pygame.K_LEFT:
                if mods & pygame.KMOD_SHIFT:
                    # Extend selection
                    if self.text_handler.agent_cursor_pos > 0:
                        self.text_handler.agent_cursor_pos -= 1
                        if self.text_handler.agent_cursor_pos < self.text_handler.agent_selection_start:
                            self.text_handler.agent_selection_start = self.text_handler.agent_cursor_pos
                        else:
                            self.text_handler.agent_selection_end = self.text_handler.agent_cursor_pos
                else:
                    # Move cursor
                    if self.text_handler.has_selection():
                        self.text_handler.agent_cursor_pos = min(self.text_handler.agent_selection_start, self.text_handler.agent_selection_end)
                        self.text_handler.agent_selection_start = self.text_handler.agent_cursor_pos
                        self.text_handler.agent_selection_end = self.text_handler.agent_cursor_pos
                    elif self.text_handler.agent_cursor_pos > 0:
                        self.text_handler.agent_cursor_pos -= 1
            elif event.key == pygame.K_RIGHT:
                if mods & pygame.KMOD_SHIFT:
                    # Extend selection
                    if self.text_handler.agent_cursor_pos < len(self.agent_prompt):
                        self.text_handler.agent_cursor_pos += 1
                        if self.text_handler.agent_cursor_pos > self.text_handler.agent_selection_end:
                            self.text_handler.agent_selection_end = self.text_handler.agent_cursor_pos
                        else:
                            self.text_handler.agent_selection_start = self.text_handler.agent_cursor_pos
                else:
                    # Move cursor
                    if self.text_handler.has_selection():
                        self.text_handler.agent_cursor_pos = max(self.text_handler.agent_selection_start, self.text_handler.agent_selection_end)
                        self.text_handler.agent_selection_start = self.text_handler.agent_cursor_pos
                        self.text_handler.agent_selection_end = self.text_handler.agent_cursor_pos
                    elif self.text_handler.agent_cursor_pos < len(self.agent_prompt):
                        self.text_handler.agent_cursor_pos += 1
            elif event.key == pygame.K_UP:
                # Move to previous line
                line, col = self.text_handler.get_line_col(self.text_handler.agent_cursor_pos, self.agent_prompt)
                if line > 0:
                    new_pos = self.text_handler.get_pos_from_line_col(line - 1, col, self.agent_prompt)
                    if mods & pygame.KMOD_SHIFT:
                        self.text_handler.agent_cursor_pos = new_pos
                        if new_pos < self.text_handler.agent_selection_start:
                            self.text_handler.agent_selection_start = new_pos
                        else:
                            self.text_handler.agent_selection_end = new_pos
                    else:
                        self.text_handler.agent_cursor_pos = new_pos
                        self.text_handler.agent_selection_start = new_pos
                        self.text_handler.agent_selection_end = new_pos
            elif event.key == pygame.K_DOWN:
                # Move to next line
                line, col = self.text_handler.get_line_col(self.text_handler.agent_cursor_pos, self.agent_prompt)
                lines = self.agent_prompt.split('\n')
                if line < len(lines) - 1:
                    new_pos = self.text_handler.get_pos_from_line_col(line + 1, col, self.agent_prompt)
                    if mods & pygame.KMOD_SHIFT:
                        self.text_handler.agent_cursor_pos = new_pos
                        if new_pos > self.text_handler.agent_selection_end:
                            self.text_handler.agent_selection_end = new_pos
                        else:
                            self.text_handler.agent_selection_start = new_pos
                    else:
                        self.text_handler.agent_cursor_pos = new_pos
                        self.text_handler.agent_selection_start = new_pos
                        self.text_handler.agent_selection_end = new_pos
            elif event.key == pygame.K_HOME:
                # Move to start of line
                line, col = self.text_handler.get_line_col(self.text_handler.agent_cursor_pos, self.agent_prompt)
                new_pos = self.text_handler.get_pos_from_line_col(line, 0, self.agent_prompt)
                if mods & pygame.KMOD_SHIFT:
                    self.text_handler.agent_cursor_pos = new_pos
                    if new_pos < self.text_handler.agent_selection_start:
                        self.text_handler.agent_selection_start = new_pos
                    else:
                        self.text_handler.agent_selection_end = new_pos
                else:
                    self.text_handler.agent_cursor_pos = new_pos
                    self.text_handler.agent_selection_start = new_pos
                    self.text_handler.agent_selection_end = new_pos
            elif event.key == pygame.K_END:
                # Move to end of line
                line, col = self.text_handler.get_line_col(self.text_handler.agent_cursor_pos, self.agent_prompt)
                lines = self.agent_prompt.split('\n')
                if line < len(lines):
                    new_pos = self.text_handler.get_pos_from_line_col(line, len(lines[line]), self.agent_prompt)
                    if mods & pygame.KMOD_SHIFT:
                        self.text_handler.agent_cursor_pos = new_pos
                        if new_pos > self.text_handler.agent_selection_end:
                            self.text_handler.agent_selection_end = new_pos
                        else:
                            self.text_handler.agent_selection_start = new_pos
                    else:
                        self.text_handler.agent_cursor_pos = new_pos
                        self.text_handler.agent_selection_start = new_pos
                        self.text_handler.agent_selection_end = new_pos
            elif event.key == pygame.K_PAGEUP:
                # Scroll up
                self.text_handler.agent_scroll_offset = max(0, self.text_handler.agent_scroll_offset - 5)
            elif event.key == pygame.K_PAGEDOWN:
                # Scroll down
                max_chars_per_line = 1000 // 8  # Approximate
                display_lines = self.text_handler.wrap_text_for_display(self.agent_prompt, max_chars_per_line)
                visible_lines = 300 // 25  # Approximate
                max_scroll = max(0, len(display_lines) - visible_lines)
                self.text_handler.agent_scroll_offset = min(max_scroll, self.text_handler.agent_scroll_offset + 5)
            elif (mods & pygame.KMOD_CTRL) and event.key == pygame.K_a:
                # Select all
                self.text_handler.select_all(self.agent_prompt)
            elif (mods & pygame.KMOD_CTRL) and event.key == pygame.K_v:
                # Paste
                try:
                    clipboard_text = pygame.scrap.get(pygame.SCRAP_TEXT).decode('utf-8')
                    # Remove null bytes and normalize line endings
                    clipboard_text = clipboard_text.replace('\x00', '').replace('\r\n', '\n').replace('\r', '\n')
                    self.agent_prompt = self.text_handler.insert_text(self.agent_prompt, clipboard_text)
                except:
                    pass  # Clipboard not available or empty
            elif (mods & pygame.KMOD_CTRL) and event.key == pygame.K_c:
                # Copy
                if self.text_handler.has_selection():
                    try:
                        selected_text = self.text_handler.get_selected_text(self.agent_prompt)
                        pygame.scrap.put(pygame.SCRAP_TEXT, selected_text.encode('utf-8'))
                    except:
                        pass  # Clipboard not available
            elif (mods & pygame.KMOD_CTRL) and event.key == pygame.K_x:
                # Cut
                if self.text_handler.has_selection():
                    try:
                        selected_text = self.text_handler.get_selected_text(self.agent_prompt)
                        pygame.scrap.put(pygame.SCRAP_TEXT, selected_text.encode('utf-8'))
                        self.agent_prompt = self.text_handler.delete_selection(self.agent_prompt)
                    except:
                        pass  # Clipboard not available
            elif event.key == pygame.K_ESCAPE:
                self.agent_prompt_focused = False
            else:
                # Add printable characters
                if event.unicode and event.unicode.isprintable():
                    self.agent_prompt = self.text_handler.insert_text(self.agent_prompt, event.unicode)

        # Handle patch name input
        elif self.current_menu == "agent" and self.patch_name_focused and not self.agent_running:
            if event.key == pygame.K_RETURN:
                # Confirm patch name and save
                self.patch_name_focused = False
                if self.patch_name.strip():
                    self.handlers.on_agent_save_patch_click()
            elif event.key == pygame.K_BACKSPACE:
                if len(self.patch_name) > 0:
                    self.patch_name = self.patch_name[:-1]
                    self.text_handler.patch_cursor_pos = len(self.patch_name)
                    self.text_handler.patch_selection_start = self.text_handler.patch_cursor_pos
                    self.text_handler.patch_selection_end = self.text_handler.patch_cursor_pos
            elif event.key == pygame.K_ESCAPE:
                self.patch_name_focused = False
            else:
                # Add printable characters
                if event.unicode and event.unicode.isprintable():
                    self.patch_name += event.unicode
                    self.text_handler.patch_cursor_pos = len(self.patch_name)
                    self.text_handler.patch_selection_start = self.text_handler.patch_cursor_pos
                    self.text_handler.patch_selection_end = self.text_handler.patch_cursor_pos

        # Handle scrolling in room menu
        elif self.current_menu == "room":
            if event.key == pygame.K_UP:
                self.scroll_offset = max(0, self.scroll_offset - 1)
            elif event.key == pygame.K_DOWN:
                max_offset = max(0, len(self.patch_manager.available_patches) - self.max_visible_patches)
                self.scroll_offset = min(max_offset, self.scroll_offset + 1)

        # Handle scrolling in library menu
        elif self.current_menu == "library":
            if event.key == pygame.K_UP:
                self.scroll_offset = max(0, self.scroll_offset - 1)
            elif event.key == pygame.K_DOWN:
                max_offset = max(0, len(self.patch_manager.available_patches) - self.max_visible_patches)
                self.scroll_offset = min(max_offset, self.scroll_offset + 1)

        # Handle scrolling in agent menu patch list
        elif self.current_menu == "agent" and not self.agent_prompt_focused and not self.patch_name_focused:
            if event.key == pygame.K_UP:
                self.agent_scroll_offset = max(0, self.agent_scroll_offset - 1)
            elif event.key == pygame.K_DOWN:
                max_offset = max(0, len(self.patch_manager.available_patches) - 14) # 14 is max_sidebar_patches
                self.agent_scroll_offset = min(max_offset, self.agent_scroll_offset + 1)

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
        """Paste clipboard content into the agent prompt."""
        system = platform.system().lower()

        # Try platform-specific clipboard first
        try:
            if system == "darwin":  # macOS
                result = subprocess.run(['pbpaste'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout:
                    clipboard_text = result.stdout
                    # Normalize line endings
                    clipboard_text = clipboard_text.replace('\r\n', '\n').replace('\r', '\n')
                    self.agent_prompt = self.text_handler.insert_text(self.agent_prompt, clipboard_text)
                    print(f"Pasted {len(clipboard_text)} characters from clipboard")
                    return

            elif system == "linux":
                # Try xclip first, then xsel
                for cmd in [['xclip', '-selection', 'clipboard', '-o'], ['xsel', '--clipboard', '--output']]:
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                        if result.returncode == 0 and result.stdout:
                            clipboard_text = result.stdout
                            # Normalize line endings
                            clipboard_text = clipboard_text.replace('\r\n', '\n').replace('\r', '\n')
                            self.agent_prompt = self.text_handler.insert_text(self.agent_prompt, clipboard_text)
                            print(f"Pasted {len(clipboard_text)} characters from clipboard")
                            return
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        continue

            elif system == "windows":
                result = subprocess.run(['powershell', 'Get-Clipboard'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout:
                    clipboard_text = result.stdout
                    # Normalize line endings
                    clipboard_text = clipboard_text.replace('\r\n', '\n').replace('\r', '\n')
                    self.agent_prompt = self.text_handler.insert_text(self.agent_prompt, clipboard_text)
                    print(f"Pasted {len(clipboard_text)} characters from clipboard")
                    return

        except Exception as e:
            print(f"Platform clipboard failed: {e}")

        # Fallback to pygame.scrap (deprecated but might work)
        try:
            # Ensure pygame.scrap is initialized
            if hasattr(pygame.scrap, 'get_init') and not pygame.scrap.get_init():
                pygame.scrap.init()

            # Try pygame.scrap
            clipboard_text = pygame.scrap.get(pygame.SCRAP_TEXT).decode('utf-8')
            # Remove null bytes and normalize line endings
            clipboard_text = clipboard_text.replace('\x00', '').replace('\r\n', '\n').replace('\r', '\n')

            if clipboard_text.strip():
                self.agent_prompt = self.text_handler.insert_text(self.agent_prompt, clipboard_text)
                print(f"Pasted {len(clipboard_text)} characters from clipboard (pygame)")
                return

        except Exception as e:
            pass

        print("Failed to paste from clipboard - try copying text first")
        print("Supported platforms: macOS, Linux (xclip/xsel), Windows")

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
                UI_called=True
            )
            self.agent_values = {"success": success, "modelHandler": modelHandler, "todo_list": todo_list, "prompt": prompt, "backup_name": backup_name}
            # Get test results
            from coding.tools.testing import run_all_tests
            test_results = run_all_tests()

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
            if self.agent_values is None:
                print("No agent values to run agent fix")
                self.show_error_message("No agent values to run agent fix")
                return
                
            from agent import full_loop

            success = self.agent_values["success"]
            modelHandler = self.agent_values["modelHandler"] 
            todo_list = self.agent_values["todo_list"]
            prompt = self.agent_values["prompt"]

            backup_name = self.agent_values.get("backup_name", "GameFolder")
            success, modelHandler, todo_list, prompt, backup_name = full_loop(prompt=prompt, modelHandler=modelHandler, todo_list=todo_list, fix_mode=True, backup_name=backup_name, total_cleanup=False, results=results, UI_called=True)
            if success:
                self.agent_values = None
            else:
                self.agent_values = {"success": success, "modelHandler": modelHandler, "todo_list": todo_list, "prompt": prompt, "backup_name": backup_name}

            # Get updated test results
            from coding.tools.testing import run_all_tests
            test_results = run_all_tests()

            # Use dictionary properties directly
            passed = test_results.get('passed_tests', 0)
            total = test_results.get('total_tests', 0)

            self.agent_results = {'passed': passed, 'total': total, 'test_output': test_results}

        except Exception as e:
            print(f"Error running agent fix: {e}")
            self.agent_results = {'passed': 0, 'total': 0, 'error': str(e)}
        finally:
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

        # CRITICAL FIX: Ensure we're applying patches from the project root directory
        # VersionControl.apply_all_changes applies patches relative to current working directory
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
                # FIXED: Actually report failure to server
                error_msg = str(errors) if errors else "Unknown error applying patches"
                self.client.send_patch_applied(success=False, error_message=error_msg)
        except Exception as e:
            print(f"Error applying patch: {e}")
            # FIXED: Actually report failure to server
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
        self.show_error_message(f"Game Over! Winner: {winner}\nServer restarting in {restart_delay} seconds...")

    def reset_room_state(self):
        """Reset all room-related states to initial values."""
        self.patches_ready = False
        self.in_room = False
        self.room_code = ""
        self.scroll_offset = 0
        # Reset any other room-specific states here

    def reset_ui_states(self):
        """Reset all UI states to prevent button states from getting stuck."""
        # Reset focus states
        self.player_id_focused = False
        self.join_room_code_focused = False
        self.agent_prompt_focused = False
        self.patch_name_focused = False

        # Reset room UI states
        self.patches_ready = False

        # Reset agent menu states
        self.agent_running = False
        self.agent_results = None
        self.show_fix_prompt = False
        self.agent_values = None
        self.agent_selected_patch_idx = -1
        self.agent_scroll_offset = 0

        # Reset text handler states
        self.text_handler.agent_cursor_pos = 0
        self.text_handler.agent_selection_start = 0
        self.text_handler.agent_selection_end = 0
        self.text_handler.agent_scroll_offset = 0
        self.text_handler.patch_cursor_pos = 0
        self.text_handler.patch_selection_start = 0
        self.text_handler.patch_selection_end = 0
        self.text_handler.patch_scroll_offset = 0

        # Reset error message state
        self.error_message = None
        self.error_message_time = 0

        # Reset target server info (for joining rooms)
        if hasattr(self, 'target_server_ip'):
            delattr(self, 'target_server_ip')
        if hasattr(self, 'target_server_port'):
            delattr(self, 'target_server_port')

        # Reset connection attempt time
        if hasattr(self, 'connection_attempt_time'):
            delattr(self, 'connection_attempt_time')

    def server_restarted_callback(self, message: str):
        """Callback when the server has restarted and is ready for new games."""
        print(f"🔄 {message}")
        print("Returning to room lobby...")

        # Reset room state and all UI states to clean slate
        self.reset_room_state()
        self.reset_ui_states()

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

    def on_start(self):
        from coding.non_callable_tools.helpers import cleanup_old_logs
        cleanup_old_logs()
        self.patch_to_apply = None
        
        # Ensure we have an initial base backup if none is set
        if self.base_working_backup is None:
            print("Creating initial safety backup...")
            try:
                from coding.non_callable_tools.backup_handling import BackupHandler
                handler = BackupHandler("__game_backups")
                _, self.base_working_backup = handler.create_backup("GameFolder")
                print(f"Initial backup created: {self.base_working_backup}")
            except Exception as e:
                print(f"Warning: Failed to create initial backup: {e}")
    
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
