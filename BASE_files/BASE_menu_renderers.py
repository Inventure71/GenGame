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
        self._init_managers()

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
        center_x = 700

        ui.add(Label(center_x, 40, "Settings", self.menu.menu_font, center=True))

        # Predefined Username
        ui.add(Label(center_x - 200, 120, "Username:", self.menu.button_font))
        ui.add(TextField(center_x - 200, 150, 400, 45, self.menu.button_font, name="settings_username"))

        # API Keys
        ui.add(Label(center_x - 200, 220, "API Keys:", self.menu.button_font))
        ui.add(Label(center_x - 200, 250, "Gemini API Key:", self.menu.small_font))
        ui.add(TextFieldWithPaste(center_x - 200, 270, 400, 45, self.menu, self.menu.button_font, name="settings_gemini_key"))
        ui.add(Label(center_x - 200, 330, "OpenAI API Key:", self.menu.small_font))
        ui.add(TextFieldWithPaste(center_x - 200, 350, 400, 45, self.menu, self.menu.button_font, name="settings_openai_key"))

        # Provider Selection
        ui.add(Label(center_x - 200, 420, "AI Provider:", self.menu.button_font))
        ui.add(Button(center_x - 200, 450, 190, 45, "GEMINI", self.menu.button_font, lambda: self._on_provider_select("GEMINI"), name="btn_gemini"))
        ui.add(Button(center_x + 10, 450, 190, 45, "OPENAI", self.menu.button_font, lambda: self._on_provider_select("OPENAI"), name="btn_openai"))

        # Model Selection
        ui.add(Label(center_x - 200, 520, "AI Model:", self.menu.button_font))
        ui.add(TextField(center_x - 200, 550, 400, 45, self.menu.button_font, name="settings_model"))

        # Save and Back buttons
        ui.add(Button(center_x - 150, 650, 140, 50, "Save", self.menu.button_font, self.menu.on_settings_save_click, style="primary"))
        ui.add(Button(center_x + 10, 650, 140, 50, "Back", self.menu.button_font, self.menu.on_settings_back_click))

    def _setup_main_menu(self):
        ui = self.managers["main"]
        center_x = 700
        
        # Player ID Field
        ui.add(TextField(center_x - 150, 20, 300, 40, self.menu.button_font, placeholder="Enter Player ID", name="player_id"))
        
        # Title
        ui.add(Label(center_x, 120, "GEN GAME", self.menu.menu_font, center=True))
        ui.add(Label(center_x, 180, "Multiplayer Gaming Platform", self.menu.small_font, center=True))

        # Buttons
        button_y = 250
        button_spacing = 80
        btns = [
            ("Create Local Room", self.menu.on_create_local_room_click, "normal"),
            ("Remote Public Game", self.menu.on_create_remote_room_click, "normal"),
            ("Join Room", self.menu.on_join_room_click, "normal"),
            ("Game Library", self.menu.on_library_click, "normal"),
            ("Agent Content", self.menu.on_agent_content_click, "normal"),
            ("Settings", self.menu.on_settings_click, "normal"),
            ("Quit", self.menu.on_quit_click, "danger")
        ]

        for text, callback, style in btns:
            ui.add(Button(center_x - 150, button_y, 300, 60, text, self.menu.button_font, callback, style=style))
            button_y += button_spacing

    def _setup_join_room_menu(self):
        ui = self.managers["join_room_code"]
        center_x = 700

        ui.add(Label(center_x, 80, "Join Room", self.menu.menu_font, center=True))
        ui.add(Label(center_x, 140, "Enter the room code to join:", self.menu.button_font, center=True))

        ui.add(TextFieldWithPaste(center_x - 200, 200, 400, 50, self.menu, self.menu.button_font, placeholder="Enter room code", name="join_code"))

        ui.add(Button(center_x - 150, 320, 300, 60, "Join Room", self.menu.button_font, self.menu.on_join_room_with_code_click, style="primary"))
        ui.add(Button(center_x - 150, 400, 300, 60, "Back to Menu", self.menu.button_font, self.menu.on_join_room_back_click))

    def _setup_room_menu(self):
        ui = self.managers["room"]
        center_x = 700
        
        ui.add(Label(center_x, 40, "Game Room", self.menu.menu_font, center=True))
        ui.add(RoomStatusBar(self.menu))
        
        ui.add(PatchBrowser(150, 130, 1100, 450, self.menu, name="patch_browser"))
        
        ui.add(Button(center_x - 150, 620, 300, 60, "Mark as Ready", self.menu.button_font, self.menu.on_ready_click, name="ready_btn"))
        ui.add(Button(center_x - 150, 700, 300, 60, "Back to Menu", self.menu.button_font, self.menu.on_back_to_menu_click))

    def _setup_library_menu(self):
        ui = self.managers["library"]
        center_x = 700
        
        ui.add(Label(center_x, 40, "Game Library", self.menu.menu_font, center=True))
        ui.add(Label(center_x, 90, "Available Patches", self.menu.small_font, center=True))
        
        # Simple read-only browser (reuse PatchBrowser component)
        ui.add(PatchBrowser(150, 130, 1100, 450, self.menu))
        
        ui.add(Button(center_x - 150, 620, 300, 60, "Back to Menu", self.menu.button_font, self.menu.on_library_back_click))

    def _setup_agent_menu(self):
        ui = self.managers["agent"]
        main_x = 410
        center_x = 860 # Center of the area to the right of sidebar (410 + 900/2)
        
        # Sidebar Panel
        ui.add(Panel(0, 0, 380, 900, color=(30, 30, 45)))
        ui.add(Label(190, 40, "Available Patches", self.menu.button_font, center=True))
        
        patch_list = ui.add(ScrollableList(10, 80, 360, 700, name="sidebar_patches"))
        patch_list.on_item_click = lambda idx, item: self.menu.handlers.on_load_patch_to_agent_click(idx)
        
        # Main Workspace (Prompt and Start Agent)
        ui.add(Label(center_x, 40, "Agent Control Center", self.menu.menu_font, center=True))
        ui.add(AgentWorkspace(main_x, 90, 900, 380, self.menu, name="agent_workspace"))
        
        # --- Bottom Section organized into sections ---
        
        # 1. Patch Saving Section
        save_y = 490
        ui.add(Panel(main_x - 10, save_y - 10, 920, 75, color=(35, 35, 50), border_width=1)) # Small frame for saving
        ui.add(Label(main_x, save_y + 5, "Patch Name:", self.menu.button_font))
        ui.add(TextField(main_x + 150, save_y, 300, 45, self.menu.button_font, name="patch_name"))
        ui.add(Button(main_x + 460, save_y, 140, 45, "Save Patch", self.menu.button_font, self.menu.on_agent_save_patch_click))
        
        # 2. Workspace Management Section (Left Column)
        mgmt_y = 585
        ui.add(Label(main_x, mgmt_y, "No patch loaded", self.menu.button_font, name="loaded_patch"))
        ui.add(Button(main_x, mgmt_y + 45, 200, 45, "Reset to Base", self.menu.button_font, self.menu.handlers.on_reset_to_base_click, style="danger"))
        ui.add(Button(main_x, mgmt_y + 105, 250, 45, "Save Current State", self.menu.button_font, self.menu.handlers.on_save_current_state_click))
        
        # 3. Test & Fix Section (Right Column)
        test_y = mgmt_y
        ui.add(Label(center_x + 150, test_y, "Results: Pending...", self.menu.button_font, center=True, name="test_results"))
        ui.add(Button(center_x + 150 - 150, test_y + 45, 300, 50, "Fix Issues", self.menu.button_font, self.menu.on_agent_fix_click, name="fix_btn"))
        
        # 4. Navigation
        ui.add(Button(center_x - 150, 820, 300, 55, "Back to Main Menu", self.menu.button_font, self.menu.on_agent_back_click))

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
