"""
Menu rendering methods for the BaseMenu class.
These methods handle rendering of different menu screens using a component-based architecture.
"""

import pygame
from BASE_files.BASE_helpers import decrypt_code
from BASE_files.BASE_ui_components import (
    UIManager, Button, TextField, Label, Panel,
    ScrollableList, RoomStatusBar, PatchBrowser,
    AgentWorkspace, TextFieldWithPaste, NotificationOverlay
)

class MenuRenderers:
    """Handles rendering of different menu screens using components."""

    def __init__(self, menu_instance):
        self.menu = menu_instance
        self.managers = {}

        # Initialize dynamic scaling system
        self._init_scaling()

        self._init_managers()

    def _init_scaling(self):
        """Initialize the dynamic scaling system for all menu components."""
        # Get screen dimensions
        self.screen_width, self.screen_height = self.menu.screen.get_size()

        # Reference dimensions (original design)
        self.REF_WIDTH, self.REF_HEIGHT = 1400, 900

        # Scaling functions
        self.scale_x = lambda x: int(x * self.screen_width / self.REF_WIDTH)
        self.scale_y = lambda y: int(y * self.screen_height / self.REF_HEIGHT)

        # Font scaling with automatic fallback
        base_scale = min(self.screen_width / self.REF_WIDTH, self.screen_height / self.REF_HEIGHT)
        self.scale_font_size = lambda size: max(12, int(size * base_scale))

        # Pre-create scaled fonts with fallback handling
        self._create_scaled_fonts()

    def _create_scaled_fonts(self):
        """Create scaled fonts with automatic fallback to system fonts."""
        try:
            self.scaled_menu_font = pygame.font.Font(None, self.scale_font_size(48))
            self.scaled_button_font = pygame.font.Font(None, self.scale_font_size(32))
            self.scaled_small_font = pygame.font.Font(None, self.scale_font_size(24))
        except Exception as e:
            print(f"Warning: Default fonts failed ({e}), using system fonts")
            try:
                self.scaled_menu_font = pygame.font.SysFont("Arial", self.scale_font_size(48))
                self.scaled_button_font = pygame.font.SysFont("Arial", self.scale_font_size(32))
                self.scaled_small_font = pygame.font.SysFont("Arial", self.scale_font_size(24))
            except Exception as e2:
                print(f"Warning: System fonts also failed ({e2}), using minimal fonts")
                # Ultimate fallback - create fonts at minimum size
                self.scaled_menu_font = pygame.font.Font(None, 12)
                self.scaled_button_font = pygame.font.Font(None, 12)
                self.scaled_small_font = pygame.font.Font(None, 12)

    def _get_scaled_fonts(self):
        """Get the appropriate fonts based on scaling (returns tuple: menu, button, small)."""
        return self.scaled_menu_font, self.scaled_button_font, self.scaled_small_font

    def _init_managers(self):
        """Initialize UIManagers for each menu state."""
        for state in ["main", "join_room_code", "room", "library", "agent", "settings"]:
            self.managers[state] = UIManager(self.menu)
            # Add global notification overlay to every manager
            self.managers[state].add(NotificationOverlay(self.menu))

        self._setup_main_menu()
        self._setup_join_room_menu()
        self._setup_room_menu()
        self._setup_library_menu()
        self._setup_agent_menu()
        self._setup_settings_menu()

    def _setup_settings_menu(self):
        ui = self.managers["settings"]
        center_x = self.screen_width // 2

        # Get scaled fonts
        menu_font, button_font, small_font = self._get_scaled_fonts()

        ui.add(Label(center_x, self.scale_y(40), "Settings", menu_font, center=True))

        # Predefined Username
        ui.add(Label(center_x - self.scale_x(200), self.scale_y(120), "Username:", button_font))
        ui.add(TextField(center_x - self.scale_x(200), self.scale_y(150), self.scale_x(400), self.scale_y(45), button_font, name="settings_username"))

        # API Keys
        ui.add(Label(center_x - self.scale_x(200), self.scale_y(220), "API Keys:", button_font))
        ui.add(Label(center_x - self.scale_x(200), self.scale_y(250), "Gemini API Key:", small_font))
        ui.add(TextFieldWithPaste(center_x - self.scale_x(200), self.scale_y(270), self.scale_x(400), self.scale_y(45), self.menu, button_font, name="settings_gemini_key"))
        ui.add(Label(center_x - self.scale_x(200), self.scale_y(330), "OpenAI API Key:", small_font))
        ui.add(TextFieldWithPaste(center_x - self.scale_x(200), self.scale_y(350), self.scale_x(400), self.scale_y(45), self.menu, button_font, name="settings_openai_key"))

        # Provider Selection
        ui.add(Label(center_x - self.scale_x(200), self.scale_y(420), "AI Provider:", button_font))
        ui.add(Button(center_x - self.scale_x(200), self.scale_y(450), self.scale_x(190), self.scale_y(45), "GEMINI", button_font, lambda: self._on_provider_select("GEMINI"), name="btn_gemini"))
        ui.add(Button(center_x + self.scale_x(10), self.scale_y(450), self.scale_x(190), self.scale_y(45), "OPENAI", button_font, lambda: self._on_provider_select("OPENAI"), name="btn_openai"))

        # Model Selection
        ui.add(Label(center_x - self.scale_x(200), self.scale_y(520), "AI Model:", button_font))
        ui.add(TextField(center_x - self.scale_x(200), self.scale_y(550), self.scale_x(400), self.scale_y(45), button_font, name="settings_model"))

        # Save and Back buttons
        ui.add(Button(center_x - self.scale_x(150), self.scale_y(650), self.scale_x(140), self.scale_y(50), "Save", button_font, self.menu.on_settings_save_click, style="primary"))
        ui.add(Button(center_x + self.scale_x(10), self.scale_y(650), self.scale_x(140), self.scale_y(50), "Back", button_font, self.menu.on_settings_back_click))

    def _setup_main_menu(self):
        ui = self.managers["main"]

        # Get scaled fonts
        menu_font, button_font, small_font = self._get_scaled_fonts()

        # Player ID Field (top center, scaled)
        player_id_width = self.scale_x(300)
        player_id_height = self.scale_y(40)
        ui.add(TextField(self.scale_x(550), self.scale_y(30), player_id_width, player_id_height, button_font, placeholder="Enter Player ID", name="player_id"))

        # Title (left side, scaled)
        ui.add(Label(self.scale_x(200), self.scale_y(90), "CORE CONFLICT", menu_font))
        ui.add(Label(self.scale_x(200), self.scale_y(150), "Multiplayer Gaming Platform", small_font))

        # Buttons layout (scaled)
        button_y = self.scale_y(200)
        button_spacing = self.scale_y(65)
        button_height = self.scale_y(55)
        button_width = self.scale_x(300)
        dual_button_width = self.scale_x(250)

        # Public Lobby (was "Remote Public Game")
        ui.add(Button(self.scale_x(550), button_y, button_width, button_height, "Public Lobby", button_font, self.menu.on_create_remote_room_click, style="normal"))
        button_y += button_spacing

        # Create Local Room and Practice Mode on same line (symmetric around screen center)
        center_x = self.screen_width // 2
        left_dual_x = center_x - dual_button_width - 5
        right_dual_x = center_x + 5

        ui.add(Button(left_dual_x, button_y, dual_button_width, button_height, "Create Local Room", button_font, self.menu.on_create_local_room_click, style="normal"))
        ui.add(Button(right_dual_x, button_y, dual_button_width, button_height, "Practice Mode", button_font, self.menu.on_practice_mode_click, style="normal"))
        button_y += button_spacing

        # Join Room
        ui.add(Button(self.scale_x(550), button_y, button_width, button_height, "Join Room", button_font, self.menu.on_join_room_click, style="normal"))
        button_y += button_spacing

        # Creator Agent (was "Agent Content")
        ui.add(Button(self.scale_x(550), button_y, button_width, button_height, "Creator Agent", button_font, self.menu.on_agent_content_click, style="normal"))
        button_y += button_spacing

        # Patches Library (was "Game Library")
        ui.add(Button(self.scale_x(550), button_y, button_width, button_height, "Patches Library", button_font, self.menu.on_library_click, style="normal"))
        button_y += button_spacing

        # Settings button (above quit)
        ui.add(Button(self.scale_x(550), button_y, button_width, button_height, "Settings", button_font, self.menu.on_settings_click, style="normal"))
        button_y += button_spacing

        # Quit
        ui.add(Button(self.scale_x(550), button_y, button_width, button_height, "Quit", button_font, self.menu.on_quit_click, style="danger"))

    def _setup_join_room_menu(self):
        ui = self.managers["join_room_code"]
        center_x = self.screen_width // 2

        # Get scaled fonts
        menu_font, button_font, small_font = self._get_scaled_fonts()

        ui.add(Label(center_x, self.scale_y(80), "Join Room", menu_font, center=True))
        ui.add(Label(center_x, self.scale_y(140), "Enter the room code to join:", button_font, center=True))

        ui.add(TextFieldWithPaste(center_x - self.scale_x(200), self.scale_y(200), self.scale_x(400), self.scale_y(50), self.menu, button_font, placeholder="Enter room code", name="join_code"))

        ui.add(Button(center_x - self.scale_x(150), self.scale_y(320), self.scale_x(300), self.scale_y(60), "Join Room", button_font, self.menu.on_join_room_with_code_click, style="primary"))
        ui.add(Button(center_x - self.scale_x(150), self.scale_y(400), self.scale_x(300), self.scale_y(60), "Back to Menu", button_font, self.menu.on_join_room_back_click))

    def _setup_room_menu(self):
        ui = self.managers["room"]
        center_x = self.screen_width // 2

        # Get scaled fonts
        menu_font, button_font, small_font = self._get_scaled_fonts()

        ui.add(Label(center_x, self.scale_y(40), "Game Room", menu_font, center=True))
        ui.add(RoomStatusBar(self.menu))

        ui.add(PatchBrowser(self.scale_x(150), self.scale_y(130), self.scale_x(1100), self.scale_y(450), self.menu, name="patch_browser"))

        ui.add(Button(center_x - self.scale_x(150), self.scale_y(620), self.scale_x(300), self.scale_y(60), "Mark as Ready", button_font, self.menu.on_ready_click, name="ready_btn"))
        ui.add(Button(center_x - self.scale_x(150), self.scale_y(700), self.scale_x(300), self.scale_y(60), "Back to Menu", button_font, self.menu.on_back_to_menu_click))

    def _setup_library_menu(self):
        ui = self.managers["library"]
        center_x = self.screen_width // 2

        # Get scaled fonts
        menu_font, button_font, small_font = self._get_scaled_fonts()

        ui.add(Label(center_x, self.scale_y(40), "Game Library", menu_font, center=True))
        ui.add(Label(center_x, self.scale_y(90), "Available Patches", small_font, center=True))

        # Simple read-only browser (reuse PatchBrowser component)
        ui.add(PatchBrowser(self.scale_x(150), self.scale_y(130), self.scale_x(1100), self.scale_y(450), self.menu))

        ui.add(Button(center_x - self.scale_x(150), self.scale_y(620), self.scale_x(300), self.scale_y(60), "Back to Menu", button_font, self.menu.on_library_back_click))

    def _setup_agent_menu(self):
        ui = self.managers["agent"]

        # Get scaled fonts
        menu_font, button_font, small_font = self._get_scaled_fonts()

        main_x = self.scale_x(410)
        center_x = main_x + self.scale_x(450)  # Center of the area to the right of sidebar

        # Sidebar Panel
        ui.add(Panel(0, 0, self.scale_x(380), self.screen_height, color=(30, 30, 45)))
        ui.add(Label(self.scale_x(190), self.scale_y(40), "Available Patches", button_font, center=True))

        patch_list = ui.add(ScrollableList(self.scale_x(10), self.scale_y(80), self.scale_x(360), self.scale_y(700), name="sidebar_patches"))
        patch_list.on_item_click = lambda idx, item: self.menu.handlers.on_load_patch_to_agent_click(idx)

        # Main Workspace (Prompt and Start Agent)
        ui.add(Label(center_x, self.scale_y(40), "Agent Control Center", menu_font, center=True))
        ui.add(AgentWorkspace(main_x, self.scale_y(90), self.scale_x(900), self.scale_y(380), self.menu, name="agent_workspace"))
        
        # --- Bottom Section organized into sections ---

        # 1. Test Results Section
        test_y = self.scale_y(500)
        ui.add(Panel(main_x - self.scale_x(10), test_y - self.scale_y(10), self.scale_x(920), self.scale_y(120), color=(35, 35, 50), border_width=1))
        ui.add(Label(center_x, test_y + self.scale_y(5), "Test Results", button_font, center=True))
        ui.add(Label(center_x, test_y + self.scale_y(30), "Results: Pending...", button_font, center=True, name="test_results"))
        ui.add(Button(center_x - self.scale_x(150), test_y + self.scale_y(50), self.scale_x(300), self.scale_y(50), "Fix Issues", button_font, self.menu.on_agent_fix_click, name="fix_btn"))

        # 2. Section to save current state as a patch
        save_y = self.scale_y(620)
        ui.add(Panel(main_x - self.scale_x(10), save_y - self.scale_y(10), self.scale_x(920), self.scale_y(90), color=(35, 35, 50), border_width=1))
        ui.add(Label(center_x, save_y + self.scale_y(5), "Save Current State as Patch", button_font, center=True))
        ui.add(Label(main_x, save_y + self.scale_y(30), "Patch Name:", button_font))
        ui.add(TextField(main_x + self.scale_x(150), save_y + self.scale_y(25), self.scale_x(300), self.scale_y(45), button_font, name="patch_name"))
        ui.add(Button(main_x + self.scale_x(460), save_y + self.scale_y(25), self.scale_x(140), self.scale_y(45), "Save Patch", button_font, self.menu.on_agent_save_patch_click))

        # 3. Big button to rebase to default state (remove patches from game folder)
        rebase_y = self.scale_y(740)
        ui.add(Panel(main_x - self.scale_x(10), rebase_y - self.scale_y(10), self.scale_x(920), self.scale_y(100), color=(45, 35, 35), border_width=2))
        ui.add(Button(center_x - self.scale_x(200), rebase_y, self.scale_x(400), self.scale_y(60), "Rebase to Default State", button_font, self.menu.handlers.on_reset_to_base_click, style="danger"))
        ui.add(Label(center_x, rebase_y + self.scale_y(70), "Remove patches from game folder", small_font, center=True))

        # 4. Navigation
        ui.add(Button(center_x - self.scale_x(150), self.scale_y(860), self.scale_x(300), self.scale_y(55), "Back to Main Menu", button_font, self.menu.on_agent_back_click))

    def _get_current_ui(self):
        return self.managers.get(self.menu.current_menu)

    def render(self):
        """Render the current menu state."""
        # Always clear the screen first to prevent artifacts from previous frames
        self.menu.screen.fill((20, 20, 30))

        ui = self._get_current_ui()
        if ui:
            # First, update component data from menu state
            self._sync_state_to_components(ui)
            ui.update()
            ui.render(self.menu.screen)

    def _sync_state_to_components(self, ui):
        """Dynamic sync of menu variables to UI components."""

        # Auto-reconnect if in room state and not connected
        if self.menu.current_menu == "room" and self.menu.in_room:
            if not (self.menu.client and self.menu.client.connected):
                if hasattr(self.menu, 'target_server_ip') and hasattr(self.menu, 'target_server_port'):
                    print(f"Auto-reconnecting to server at {self.menu.target_server_ip}:{self.menu.target_server_port}...")
                    if self.menu.network.connect_to_server(self.menu.target_server_ip, self.menu.target_server_port):
                        print("Reconnected successfully!")
                    else:
                        print("Failed to auto-reconnect")


        # This bridge replaces the dynamic parts of old renderers
        for comp in ui.components:
            if comp.name == "player_id":
                if not comp.focused:
                    # Use settings username as default if player_id is empty
                    if not self.menu.player_id and getattr(self.menu, 'settings_username', ''):
                        comp.text = self.menu.settings_username
                    else:
                        comp.text = self.menu.player_id
                else:
                    self.menu.player_id = comp.text
                    # Also update settings username to keep them in sync
                    self.menu.settings_username = comp.text
            elif comp.name == "join_code":
                if not comp.focused: comp.text = self.menu.join_room_code
                else: self.menu.join_room_code = comp.text
            elif comp.name == "patch_name":
                if not comp.focused: comp.text = self.menu.patch_name
                else: self.menu.patch_name = comp.text
            elif comp.name == "ready_btn":
                comp.text = "Ready!" if self.menu.patches_ready else "Mark as Ready"
            elif comp.name == "test_results":
                if self.menu.agent_results:
                    passed = self.menu.agent_results['passed']
                    total = self.menu.agent_results['total']
                    comp.text = f"Tests: {passed}/{total} Passed"
                    comp.color = (100, 255, 100) if passed == total else (255, 100, 100)
            elif comp.name == "fix_btn":
                comp.visible = bool(self.menu.agent_results and self.menu.agent_results['passed'] < self.menu.agent_results['total'])
                comp.enabled = not self.menu.agent_running
            elif comp.name == "settings_username":
                if not comp.focused: comp.text = getattr(self.menu, 'settings_username', '')
                else: self.menu.settings_username = comp.text
            elif comp.name == "settings_gemini_key":
                if not comp.focused: comp.text = getattr(self.menu, 'settings_gemini_key', '')
                else: self.menu.settings_gemini_key = comp.text
            elif comp.name == "settings_openai_key":
                if not comp.focused: comp.text = getattr(self.menu, 'settings_openai_key', '')
                else: self.menu.settings_openai_key = comp.text
            elif comp.name == "settings_model":
                if not comp.focused: comp.text = getattr(self.menu, 'settings_model', '')
                else: self.menu.settings_model = comp.text
            elif comp.name in ["btn_gemini", "btn_openai"] and self.menu.current_menu == "settings":
                # Update button styles based on selected provider
                provider = getattr(self.menu, 'selected_provider', 'GEMINI')
                if comp.name == "btn_gemini":
                    comp.style = "primary" if provider == "GEMINI" else "normal"
                elif comp.name == "btn_openai":
                    comp.style = "primary" if provider == "OPENAI" else "normal"
            elif comp.name == "sidebar_patches" and self.menu.current_menu == "agent":
                # Refresh if count changed, loaded patch changed, or it's empty
                current_loaded_idx = getattr(self.menu, 'agent_selected_patch_idx', -1)
                should_refresh = (
                    len(comp.items) != len(self.menu.patch_manager.available_patches) or
                    not hasattr(comp, 'last_loaded_idx') or
                    comp.last_loaded_idx != current_loaded_idx
                )

                if should_refresh:
                    # Store current scroll position
                    current_scroll = comp.scroll_offset
                    comp.clear_items()
                    for i, patch in enumerate(self.menu.patch_manager.available_patches):
                        name = patch.name if len(patch.name) < 25 else patch.name[:22] + "..."
                        # Mark currently loaded patch with [LOADED]
                        if i == current_loaded_idx:
                            display_name = f"[LOADED] {name} ({patch.num_changes})"
                        else:
                            display_name = f"{name} ({patch.num_changes})"
                        comp.add_item(display_name, patch)
                    comp.last_loaded_idx = current_loaded_idx
                    # Restore scroll position
                    comp.scroll_offset = current_scroll
            elif comp.name == "loaded_patch":
                # Update the loaded patch indicator
                if hasattr(self.menu, 'agent_selected_patch_idx') and self.menu.agent_selected_patch_idx >= 0:
                    try:
                        patch = self.menu.patch_manager.available_patches[self.menu.agent_selected_patch_idx]
                        comp.text = f"Loaded: {patch.name}"
                        comp.color = (100, 200, 255)  # Blue for loaded
                    except (IndexError, AttributeError):
                        comp.text = "No patch loaded"
                        comp.color = (150, 150, 150)
                else:
                    comp.text = "No patch loaded"
                    comp.color = (150, 150, 150)

    def render_main_menu(self): self.render()
    def render_join_room_code_menu(self): self.render()
    def render_room_menu(self): self.render()
    def render_library_menu(self): self.render()
    def render_agent_menu(self): self.render()
    def render_settings_menu(self): self.render()


    def _on_provider_select(self, provider):
        """Handle provider selection in settings."""
        self.menu.selected_provider = provider
        # Update button styles to show selection
        ui = self.managers["settings"]
        for comp in ui.components:
            if comp.name == "btn_gemini":
                comp.style = "primary" if provider == "GEMINI" else "normal"
            elif comp.name == "btn_openai":
                comp.style = "primary" if provider == "OPENAI" else "normal"
