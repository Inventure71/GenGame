"""
Menu rendering methods for the BaseMenu class.
These methods handle rendering of different menu screens.
"""

import pygame
from BASE_files.BASE_helpers import decrypt_code

class MenuRenderers:
    """Handles rendering of different menu screens."""

    def __init__(self, menu_instance):
        self.menu = menu_instance

    def render_main_menu(self):
        """Render the main menu."""
        self.menu.screen.fill(self.menu.menu_background_color)

        # Player ID text field at the top
        field_width = 300
        field_height = 40
        field_x = (1400 - field_width) // 2  # Center horizontally
        field_y = 20

        player_id_rect = self.menu.utils.draw_text_field(self.menu.player_id, field_x, field_y, field_width, field_height,
                                             self.menu.player_id_focused, "Enter Player ID")

        # Handle clicking on the text field
        if self.menu.utils.check_button_click(player_id_rect, self.menu.mouse_clicked, self.menu.mouse_pos):
            self.menu.player_id_focused = True
        elif self.menu.mouse_clicked and not player_id_rect.collidepoint(self.menu.mouse_pos):
            self.menu.player_id_focused = False

        # Title
        self.menu.utils.draw_text("GEN GAME", 700, 120, self.menu.menu_font, center=True)

        # Subtitle
        self.menu.utils.draw_text("Multiplayer Gaming Platform", 700, 180, self.menu.small_font, center=True)

        # Buttons
        center_x = 700
        button_y = 250  # Moved down to make room for player ID field
        button_spacing = 80

        # Create Local Room Button
        create_local_rect = self.menu.utils.draw_button("Create Local Room", center_x - self.menu.utils.button_width//2, button_y,
                                            self.menu.utils.button_width, self.menu.utils.button_height,
                                            self.menu.utils.check_button_hover(center_x - self.menu.utils.button_width//2, button_y, self.menu.utils.button_width, self.menu.utils.button_height, self.menu.mouse_pos))
        if self.menu.utils.check_button_click(create_local_rect, self.menu.mouse_clicked, self.menu.mouse_pos):
            self.menu.on_create_local_room_click()

        # Create Remote Room Button
        create_remote_rect = self.menu.utils.draw_button("Create Remote Room", center_x - self.menu.utils.button_width//2, button_y + button_spacing,
                                             self.menu.utils.button_width, self.menu.utils.button_height,
                                             self.menu.utils.check_button_hover(center_x - self.menu.utils.button_width//2, button_y + button_spacing, self.menu.utils.button_width, self.menu.utils.button_height, self.menu.mouse_pos))
        if self.menu.utils.check_button_click(create_remote_rect, self.menu.mouse_clicked, self.menu.mouse_pos):
            self.menu.on_create_remote_room_click()

        # Join Room Button
        join_rect = self.menu.utils.draw_button("Join Room", center_x - self.menu.utils.button_width//2, button_y + button_spacing * 2,
                                    self.menu.utils.button_width, self.menu.utils.button_height,
                                    self.menu.utils.check_button_hover(center_x - self.menu.utils.button_width//2, button_y + button_spacing * 2, self.menu.utils.button_width, self.menu.utils.button_height, self.menu.mouse_pos))
        if self.menu.utils.check_button_click(join_rect, self.menu.mouse_clicked, self.menu.mouse_pos):
            self.menu.on_join_room_click()

        # Library Button
        library_rect = self.menu.utils.draw_button("Game Library", center_x - self.menu.utils.button_width//2, button_y + button_spacing * 3,
                                       self.menu.utils.button_width, self.menu.utils.button_height,
                                       self.menu.utils.check_button_hover(center_x - self.menu.utils.button_width//2, button_y + button_spacing * 3, self.menu.utils.button_width, self.menu.utils.button_height, self.menu.mouse_pos))
        if self.menu.utils.check_button_click(library_rect, self.menu.mouse_clicked, self.menu.mouse_pos):
            self.menu.on_library_click()

        # Agent Content Button
        agent_rect = self.menu.utils.draw_button("Agent Content", center_x - self.menu.utils.button_width//2, button_y + button_spacing * 4,
                                     self.menu.utils.button_width, self.menu.utils.button_height,
                                     self.menu.utils.check_button_hover(center_x - self.menu.utils.button_width//2, button_y + button_spacing * 4, self.menu.utils.button_width, self.menu.utils.button_height, self.menu.mouse_pos))
        if self.menu.utils.check_button_click(agent_rect, self.menu.mouse_clicked, self.menu.mouse_pos):
            self.menu.on_agent_content_click()

        # Settings Button
        settings_rect = self.menu.utils.draw_button("Settings", center_x - self.menu.utils.button_width//2, button_y + button_spacing * 5,
                                        self.menu.utils.button_width, self.menu.utils.button_height,
                                        self.menu.utils.check_button_hover(center_x - self.menu.utils.button_width//2, button_y + button_spacing * 5, self.menu.utils.button_width, self.menu.utils.button_height, self.menu.mouse_pos))
        if self.menu.utils.check_button_click(settings_rect, self.menu.mouse_clicked, self.menu.mouse_pos):
            self.menu.on_settings_click()

        # Quit Button
        quit_rect = self.menu.utils.draw_button("Quit", center_x - self.menu.utils.button_width//2, button_y + button_spacing * 6,
                                    self.menu.utils.button_width, self.menu.utils.button_height,
                                    self.menu.utils.check_button_hover(center_x - self.menu.utils.button_width//2, button_y + button_spacing * 6, self.menu.utils.button_width, self.menu.utils.button_height, self.menu.mouse_pos))
        if self.menu.utils.check_button_click(quit_rect, self.menu.mouse_clicked, self.menu.mouse_pos):
            self.menu.on_quit_click()

        # Show error message if any (for a few seconds)
        if self.menu.error_message and pygame.time.get_ticks() - self.menu.error_message_time < 5000:  # 5 seconds
            self.menu.utils.draw_text(self.menu.error_message, 700, 550, self.menu.small_font, color=(255, 100, 100), center=True)
        elif self.menu.error_message:
            # Clear old error message
            self.menu.error_message = None

    def render_room_menu(self):
        """Render the room menu with patch manager."""
        self.menu.screen.fill(self.menu.menu_background_color)

        # Try to connect if not already connected (happens when entering room)
        # For joining clients, this will establish the connection
        # For hosts, they should already be connected from create_room()
        if not self.menu.client or not self.menu.client.connected:
            connection_attempt_time = getattr(self.menu, 'connection_attempt_time', 0)
            current_time = pygame.time.get_ticks()

            # Only attempt connection once every 3 seconds to avoid spam
            if current_time - connection_attempt_time > 3000:
                self.menu.connection_attempt_time = current_time
                print("Attempting to connect to room...")

                # Check if we have target server info (from joining with code)
                if hasattr(self.menu, 'target_server_ip') and hasattr(self.menu, 'target_server_port'):
                    # Connect to the specific server from the room code
                    if not self.menu.network.connect_to_server(self.menu.target_server_ip, self.menu.target_server_port):
                        # Connection failed - show error and return to join room code menu
                        self.menu.show_error_message("Failed to connect to room - server not found")
                        self.menu.show_menu("join_room_code")
                        return
                else:
                    # Default behavior - connect to localhost (for local rooms)
                    if not self.menu.network.connect_to_server():
                        # Connection failed - show error and return to main menu
                        self.menu.show_error_message("Failed to connect to room - no server found")
                        self.menu.show_menu("main")
                        return

        # Scan patches if not done yet
        if not self.menu.patch_manager.available_patches:
            self.menu.patch_manager.scan_patches()

        # Title
        self.menu.utils.draw_text("Game Room", 700, 40, self.menu.menu_font, center=True)

        # Room code display
        if self.menu.room_code:
                # Fallback if code can't be decrypted
                self.menu.utils.draw_text(f"Room Code: {self.menu.room_code}", 700, 85, self.menu.small_font, center=True)
                self.menu.utils.draw_text("Share this code with others to let them join", 700, 110, self.menu.small_font, color=(150, 150, 150), center=True)
        else:
            # No room code set
            self.menu.utils.draw_text("Room Lobby", 700, 85, self.menu.small_font, center=True)
            self.menu.utils.draw_text("Waiting for other players...", 700, 110, self.menu.small_font, color=(150, 150, 150), center=True)

        # Room status
        status_y = 135 if self.menu.room_code else 90
        status_text = f"Status: {'Connected' if self.menu.client and self.menu.client.connected else 'Connecting...'}"
        self.menu.utils.draw_text(status_text, 700, status_y, self.menu.small_font, center=True)

        # === PATCH MANAGER UI ===
        patch_panel_x = 150
        patch_panel_y = 130
        patch_panel_width = 1100
        patch_panel_height = 450

        # Draw patch panel background
        pygame.draw.rect(self.menu.screen, (30, 30, 40),
                        (patch_panel_x, patch_panel_y, patch_panel_width, patch_panel_height))
        pygame.draw.rect(self.menu.screen, (100, 100, 120),
                        (patch_panel_x, patch_panel_y, patch_panel_width, patch_panel_height), 2)

        # Patch selection title
        self.menu.utils.draw_text(f"Select Patches (0-3) - {len(self.menu.patch_manager.selected_patches)}/3 selected",
                      patch_panel_x + 10, patch_panel_y + 10, self.menu.utils.button_font)

        # Scrollable patch list
        list_start_y = patch_panel_y + 50
        item_height = 45

        patches = self.menu.patch_manager.available_patches
        visible_patches = patches[self.menu.scroll_offset:self.menu.scroll_offset + self.menu.max_visible_patches]

        for i, patch in enumerate(visible_patches):
            actual_index = self.menu.scroll_offset + i
            item_y = list_start_y + i * item_height

            # Draw patch item background
            item_color = (50, 100, 50) if patch.selected else (50, 50, 60)
            item_rect = pygame.Rect(patch_panel_x + 10, item_y, patch_panel_width - 20, item_height - 5)

            # Check if mouse hovering
            is_hovered = item_rect.collidepoint(self.menu.mouse_pos)
            if is_hovered and not patch.selected:
                item_color = (70, 70, 80)

            pygame.draw.rect(self.menu.screen, item_color, item_rect, border_radius=5)
            pygame.draw.rect(self.menu.screen, (150, 150, 180), item_rect, 2, border_radius=5)

            # Check for click
            if self.menu.utils.check_button_click(item_rect, self.menu.mouse_clicked, self.menu.mouse_pos):
                self.menu.patch_manager.toggle_selection(actual_index)

            # Draw patch info
            checkbox = "[X]" if patch.selected else "[ ]"
            text = f"{checkbox} {patch.name} (Base: {patch.base_backup}, Changes: {patch.num_changes})"
            self.menu.utils.draw_text(text, patch_panel_x + 20, item_y + 12, self.menu.small_font)

        # Scroll indicators
        if self.menu.scroll_offset > 0:
            self.menu.utils.draw_text("▲ Scroll Up", patch_panel_x + patch_panel_width - 120, patch_panel_y + 10,
                          self.menu.small_font, color=(200, 200, 255))
        if self.menu.scroll_offset + self.menu.max_visible_patches < len(patches):
            self.menu.utils.draw_text("▼ Scroll Down", patch_panel_x + patch_panel_width - 120,
                          patch_panel_y + patch_panel_height - 30,
                          self.menu.small_font, color=(200, 200, 255))

        # Show no patches message if empty
        if not patches:
            self.menu.utils.draw_text("No patches found in __patches directory",
                          700, patch_panel_y + 200, self.menu.utils.button_font, center=True)

        # === BUTTONS ===
        center_x = 700
        button_y = 620
        button_spacing = 80

        # Ready/Start Game Button (only show if connected)
        if self.menu.client and self.menu.client.connected:
            ready_text = "Ready!" if self.menu.patches_ready else "Mark as Ready"
            ready_color = self.menu.utils.button_hover_color if self.menu.patches_ready else self.menu.utils.button_color

            ready_rect = pygame.Rect(center_x - self.menu.utils.button_width//2, button_y,
                                    self.menu.utils.button_width, self.menu.utils.button_height)
            pygame.draw.rect(self.menu.screen, ready_color, ready_rect, border_radius=8)
            pygame.draw.rect(self.menu.screen, (150, 150, 180), ready_rect, 2, border_radius=8)

            text_surf = self.menu.utils.button_font.render(ready_text, True, self.menu.utils.button_text_color)
            text_rect = text_surf.get_rect(center=ready_rect.center)
            self.menu.screen.blit(text_surf, text_rect)

            if self.menu.utils.check_button_click(ready_rect, self.menu.mouse_clicked, self.menu.mouse_pos):
                self.menu.on_ready_click()
            button_y += button_spacing

        # Back to Menu Button
        back_rect = self.menu.utils.draw_button("Back to Menu", center_x - self.menu.utils.button_width//2, button_y,
                                    self.menu.utils.button_width, self.menu.utils.button_height,
                                    self.menu.utils.check_button_hover(center_x - self.menu.utils.button_width//2, button_y, self.menu.utils.button_width, self.menu.utils.button_height, self.menu.mouse_pos))
        if self.menu.utils.check_button_click(back_rect, self.menu.mouse_clicked, self.menu.mouse_pos):
            self.menu.on_back_to_menu_click()

        # Show error message if any (for a few seconds)
        if self.menu.error_message and pygame.time.get_ticks() - self.menu.error_message_time < 5000:  # 5 seconds
            self.menu.utils.draw_text(self.menu.error_message, 700, 850, self.menu.small_font, color=(255, 100, 100), center=True)
        elif self.menu.error_message:
            # Clear old error message
            self.menu.error_message = None

    def render_join_room_code_menu(self):
        """Render the join room code entry menu."""
        self.menu.screen.fill(self.menu.menu_background_color)

        # Title
        self.menu.utils.draw_text("Join Room", 700, 80, self.menu.menu_font, center=True)

        # Instructions
        self.menu.utils.draw_text("Enter the room code to join:", 700, 140, self.menu.utils.button_font, center=True)

        # Room code text field
        field_width = 400
        field_height = 50
        field_x = (1400 - field_width) // 2
        field_y = 200

        room_code_rect = self.menu.utils.draw_text_field(self.menu.join_room_code, field_x, field_y, field_width, field_height,
                                             self.menu.join_room_code_focused, "Enter room code")

        # Handle clicking on the text field
        if self.menu.utils.check_button_click(room_code_rect, self.menu.mouse_clicked, self.menu.mouse_pos):
            self.menu.join_room_code_focused = True
        elif self.menu.mouse_clicked and not room_code_rect.collidepoint(self.menu.mouse_pos):
            self.menu.join_room_code_focused = False

        # Buttons
        center_x = 700
        button_y = 320
        button_spacing = 80

        # Join Room Button
        join_rect = self.menu.utils.draw_button("Join Room", center_x - self.menu.utils.button_width//2, button_y,
                                    self.menu.utils.button_width, self.menu.utils.button_height,
                                    self.menu.utils.check_button_hover(center_x - self.menu.utils.button_width//2, button_y, self.menu.utils.button_width, self.menu.utils.button_height, self.menu.mouse_pos))
        if self.menu.utils.check_button_click(join_rect, self.menu.mouse_clicked, self.menu.mouse_pos):
            self.menu.on_join_room_with_code_click()

        # Back to Menu Button
        back_rect = self.menu.utils.draw_button("Back to Menu", center_x - self.menu.utils.button_width//2, button_y + button_spacing,
                                    self.menu.utils.button_width, self.menu.utils.button_height,
                                    self.menu.utils.check_button_hover(center_x - self.menu.utils.button_width//2, button_y + button_spacing, self.menu.utils.button_width, self.menu.utils.button_height, self.menu.mouse_pos))
        if self.menu.utils.check_button_click(back_rect, self.menu.mouse_clicked, self.menu.mouse_pos):
            self.menu.on_join_room_back_click()

        # Show error message if any
        if self.menu.error_message and pygame.time.get_ticks() - self.menu.error_message_time < 5000:  # 5 seconds
            self.menu.utils.draw_text(self.menu.error_message, 700, 550, self.menu.small_font, color=(255, 100, 100), center=True)
        elif self.menu.error_message:
            self.menu.error_message = None

    def render_library_menu(self):
        """Render the game library menu."""
        self.menu.screen.fill(self.menu.menu_background_color)

        # Title
        self.menu.utils.draw_text("Game Library", 700, 40, self.menu.menu_font, center=True)
        self.menu.utils.draw_text("Available Patches", 700, 90, self.menu.small_font, center=True)

        # Scan patches if not done yet
        if not self.menu.patch_manager.available_patches:
            self.menu.patch_manager.scan_patches()

        # === PATCH DISPLAY PANEL ===
        patch_panel_x = 150
        patch_panel_y = 130
        patch_panel_width = 1100
        patch_panel_height = 450

        # Draw patch panel background
        pygame.draw.rect(self.menu.screen, (30, 30, 40),
                        (patch_panel_x, patch_panel_y, patch_panel_width, patch_panel_height))
        pygame.draw.rect(self.menu.screen, (100, 100, 120),
                        (patch_panel_x, patch_panel_y, patch_panel_width, patch_panel_height), 2)

        # Patch list title
        patches = self.menu.patch_manager.available_patches
        self.menu.utils.draw_text(f"Available Patches: {len(patches)}",
                      patch_panel_x + 10, patch_panel_y + 10, self.menu.utils.button_font)

        # Scrollable patch list
        list_start_y = patch_panel_y + 50
        item_height = 45

        visible_patches = patches[self.menu.scroll_offset:self.menu.scroll_offset + self.menu.max_visible_patches]

        for i, patch in enumerate(visible_patches):
            actual_index = self.menu.scroll_offset + i
            item_y = list_start_y + i * item_height

            # Draw patch item background
            item_color = (50, 50, 60)
            item_rect = pygame.Rect(patch_panel_x + 10, item_y, patch_panel_width - 20, item_height - 5)

            # Check if mouse hovering
            is_hovered = item_rect.collidepoint(self.menu.mouse_pos)
            if is_hovered:
                item_color = (70, 70, 80)

            pygame.draw.rect(self.menu.screen, item_color, item_rect, border_radius=5)
            pygame.draw.rect(self.menu.screen, (150, 150, 180), item_rect, 2, border_radius=5)

            # Draw patch info (no checkbox since it's view-only)
            text = f"{patch.name} (Base: {patch.base_backup}, Changes: {patch.num_changes})"
            self.menu.utils.draw_text(text, patch_panel_x + 20, item_y + 12, self.menu.small_font)

        # Scroll indicators
        if self.menu.scroll_offset > 0:
            self.menu.utils.draw_text("▲ Scroll Up", patch_panel_x + patch_panel_width - 120, patch_panel_y + 10,
                          self.menu.small_font, color=(200, 200, 255))
        if self.menu.scroll_offset + self.menu.max_visible_patches < len(patches):
            self.menu.utils.draw_text("▼ Scroll Down", patch_panel_x + patch_panel_width - 120,
                          patch_panel_y + patch_panel_height - 30,
                          self.menu.small_font, color=(200, 200, 255))

        # Show no patches message if empty
        if not patches:
            self.menu.utils.draw_text("No patches found in __patches directory",
                          700, patch_panel_y + 200, self.menu.utils.button_font, center=True)

        # === BUTTONS ===
        center_x = 700
        button_y = 620
        button_spacing = 80

        # Back Button
        back_rect = self.menu.utils.draw_button("Back to Menu", center_x - self.menu.utils.button_width//2, button_y,
                                    self.menu.utils.button_width, self.menu.utils.button_height,
                                    self.menu.utils.check_button_hover(center_x - self.menu.utils.button_width//2, button_y, self.menu.utils.button_width, self.menu.utils.button_height, self.menu.mouse_pos))
        if self.menu.utils.check_button_click(back_rect, self.menu.mouse_clicked, self.menu.mouse_pos):
            self.menu.on_library_back_click()

    def render_agent_menu(self):
        """Render the improved agent content creation menu with patch selection and state saving."""
        self.menu.screen.fill(self.menu.menu_background_color)

        # Draw sidebar background
        sidebar_width = 380
        pygame.draw.rect(self.menu.screen, (30, 30, 45), (0, 0, sidebar_width, 900))
        pygame.draw.line(self.menu.screen, (100, 100, 130), (sidebar_width, 0), (sidebar_width, 900), 2)

        # --- SIDEBAR: PATCH LIST ---
        self.menu.utils.draw_text("Available Patches", 190, 40, self.menu.button_font, center=True)
        
        # Scan patches if not done yet
        if not self.menu.patch_manager.available_patches:
            self.menu.patch_manager.scan_patches()

        patches = self.menu.patch_manager.available_patches
        patch_list_y = 80
        patch_item_height = 50
        max_sidebar_patches = 14
        
        visible_patches = patches[self.menu.agent_scroll_offset:self.menu.agent_scroll_offset + max_sidebar_patches]

        for i, patch in enumerate(visible_patches):
            actual_idx = self.menu.agent_scroll_offset + i
            item_y = patch_list_y + i * patch_item_height
            
            # Highlight selected patch
            is_selected = (self.menu.agent_selected_patch_idx == actual_idx)
            item_color = (60, 60, 100) if is_selected else (45, 45, 65)
            
            item_rect = pygame.Rect(10, item_y, sidebar_width - 20, patch_item_height - 5)
            is_hovered = item_rect.collidepoint(self.menu.mouse_pos)
            if is_hovered and not is_selected:
                item_color = (70, 70, 90)
            
            pygame.draw.rect(self.menu.screen, item_color, item_rect, border_radius=5)
            pygame.draw.rect(self.menu.screen, (100, 100, 130), item_rect, 1, border_radius=5)
            
            # Patch name and info
            name_text = patch.name if len(patch.name) < 25 else patch.name[:22] + "..."
            self.menu.utils.draw_text(name_text, 25, item_y + 8, self.menu.small_font)
            self.menu.utils.draw_text(f"Changes: {patch.num_changes}", 25, item_y + 26, self.menu.small_font, color=(180, 180, 180))

            # Load Button for each patch
            load_btn_width = 80
            load_btn_rect = pygame.Rect(sidebar_width - load_btn_width - 20, item_y + 8, load_btn_width, 30)
            load_hovered = load_btn_rect.collidepoint(self.menu.mouse_pos)
            load_color = (100, 100, 200) if load_hovered else (70, 70, 150)
            
            pygame.draw.rect(self.menu.screen, load_color, load_btn_rect, border_radius=4)
            load_text = self.menu.small_font.render("Load", True, (255, 255, 255))
            load_text_rect = load_text.get_rect(center=load_btn_rect.center)
            self.menu.screen.blit(load_text, load_text_rect)

            if self.menu.utils.check_button_click(load_btn_rect, self.menu.mouse_clicked, self.menu.mouse_pos) and not self.menu.agent_running:
                self.menu.handlers.on_load_patch_to_agent_click(actual_idx)

        # Sidebar scroll indicators
        if self.menu.agent_scroll_offset > 0:
            self.menu.utils.draw_text("▲", sidebar_width - 30, patch_list_y - 25, self.menu.small_font)
        if self.menu.agent_scroll_offset + max_sidebar_patches < len(patches):
            self.menu.utils.draw_text("▼", sidebar_width - 30, patch_list_y + (max_sidebar_patches * patch_item_height), self.menu.small_font)

        # --- MAIN AREA: AGENT CONTROLS ---
        main_x_center = sidebar_width + (1400 - sidebar_width) // 2
        
        # Title
        self.menu.utils.draw_text("Agent Control Center", main_x_center, 40, self.menu.menu_font, center=True)

        # Prompt Section
        prompt_y = 110
        prompt_width = 900
        prompt_height = 280
        prompt_x = main_x_center - prompt_width // 2

        self.menu.utils.draw_text("Describe features or improvements:", prompt_x, prompt_y - 30, self.menu.button_font)

        prompt_rect = pygame.Rect(prompt_x, prompt_y, prompt_width, prompt_height)
        pygame.draw.rect(self.menu.screen, (40, 40, 50), prompt_rect)
        pygame.draw.rect(self.menu.screen, (100, 100, 120), prompt_rect, 2)

        if self.menu.utils.check_button_click(prompt_rect, self.menu.mouse_clicked, self.menu.mouse_pos) and not self.menu.agent_running:
            self.menu.agent_prompt_focused = True
            self.menu.text_handler.update_cursor_from_mouse_click(prompt_rect, prompt_y, self.menu.mouse_pos, self.menu.agent_prompt)
        elif self.menu.mouse_clicked and not prompt_rect.collidepoint(self.menu.mouse_pos):
            self.menu.agent_prompt_focused = False

        if self.menu.agent_prompt_focused:
            pygame.draw.rect(self.menu.screen, (150, 150, 180), prompt_rect, 3)

        self.menu.text_handler.draw_text_input(prompt_rect, prompt_y, prompt_width, prompt_height, self.menu.agent_prompt, self.menu.screen, self.menu.utils.button_font, self.menu.menu_text_color, self.menu.frame_count)

        # Action Buttons Area
        btn_y = prompt_y + prompt_height + 25
        
        # Paste Button
        paste_rect = self.menu.utils.draw_button("Paste", prompt_x, btn_y, 150, 50, 
                                     self.menu.utils.check_button_hover(prompt_x, btn_y, 150, 50, self.menu.mouse_pos))
        if self.menu.utils.check_button_click(paste_rect, self.menu.mouse_clicked, self.menu.mouse_pos) and not self.menu.agent_running:
            self.menu.paste_clipboard()

        # Run Button
        run_text = "Running Agent..." if self.menu.agent_running else "Start Agent"
        run_btn_width = 300
        run_x = main_x_center - run_btn_width // 2
        run_rect = self.menu.utils.draw_button(run_text, run_x, btn_y, run_btn_width, 50,
                                   self.menu.utils.check_button_hover(run_x, btn_y, run_btn_width, 50, self.menu.mouse_pos))
        if self.menu.utils.check_button_click(run_rect, self.menu.mouse_clicked, self.menu.mouse_pos) and not self.menu.agent_running and self.menu.agent_prompt.strip():
            self.menu.on_agent_send_click()

        # Status & Monitor Info
        monitor_y = btn_y + 70
        self.menu.utils.draw_text("Live Monitor: http://127.0.0.1:8765", main_x_center, monitor_y, self.menu.small_font, center=True, color=(150, 200, 255))

        # Divider
        pygame.draw.line(self.menu.screen, (80, 80, 100), (sidebar_width + 50, monitor_y + 30), (1350, monitor_y + 30), 1)

        # Results & Persistence Section
        lower_y = monitor_y + 60

        # Always show patch saving section (moved up so it's always visible)
        save_panel_width = 600
        save_panel_x = main_x_center - save_panel_width // 2

        self.menu.utils.draw_text("Patch Name:", save_panel_x, lower_y + 10, self.menu.button_font)

        patch_name_rect = pygame.Rect(save_panel_x + 150, lower_y, 300, 45)
        pygame.draw.rect(self.menu.screen, (40, 40, 50), patch_name_rect)
        pygame.draw.rect(self.menu.screen, (100, 100, 120), patch_name_rect, 2)

        if self.menu.utils.check_button_click(patch_name_rect, self.menu.mouse_clicked, self.menu.mouse_pos) and not self.menu.agent_running:
            self.menu.patch_name_focused = True
            self.menu.agent_prompt_focused = False
            self.menu.text_handler.update_patch_cursor_from_mouse_click(patch_name_rect, lower_y, self.menu.mouse_pos, self.menu.patch_name)

        if self.menu.patch_name_focused:
            pygame.draw.rect(self.menu.screen, (150, 150, 180), patch_name_rect, 3)

        self.menu.text_handler.draw_patch_text_input(patch_name_rect, lower_y, 300, 45, self.menu.patch_name, self.menu.screen, self.menu.button_font, self.menu.menu_text_color, self.menu.patch_name_focused)

        button_y = lower_y + 60

        # Save Patch Button
        save_rect = self.menu.utils.draw_button("Save Patch", save_panel_x + 460, button_y, 140, 45,
                                    self.menu.utils.check_button_hover(save_panel_x + 460, button_y, 140, 45, self.menu.mouse_pos))
        if self.menu.utils.check_button_click(save_rect, self.menu.mouse_clicked, self.menu.mouse_pos) and self.menu.patch_name.strip():
            self.menu.on_agent_save_patch_click()

        # "Save Current State" Button (Always available emergency save)
        state_btn_width = 250
        state_rect = self.menu.utils.draw_button("Save Current State", save_panel_x, button_y, state_btn_width, 45,
                                     self.menu.utils.check_button_hover(save_panel_x, button_y, state_btn_width, 45, self.menu.mouse_pos))
        if self.menu.utils.check_button_click(state_rect, self.menu.mouse_clicked, self.menu.mouse_pos):
            self.menu.handlers.on_save_current_state_click()

        # Show test results and fix button if we have results
        if self.menu.agent_results or self.menu.agent_values:
            results_y = button_y + 70

            # Show Test Results if any
            res_text = "Results pending..."
            if self.menu.agent_results:
                passed = self.menu.agent_results['passed']
                total = self.menu.agent_results['total']
                res_text = f"Tests: {passed}/{total} Passed"
                color = (100, 255, 100) if passed == total else (255, 100, 100)
                self.menu.utils.draw_text(res_text, main_x_center, results_y, self.menu.button_font, center=True, color=color)

            # Fix Issues button (only show if there were failures)
            if self.menu.agent_results and self.menu.agent_results['passed'] < self.menu.agent_results['total']:
                fix_y = results_y + 50
                fix_rect = self.menu.utils.draw_button("Fix Issues", main_x_center - 150, fix_y, 300, 50,
                                           self.menu.utils.check_button_hover(main_x_center - 150, fix_y, 300, 50, self.menu.mouse_pos))
                if self.menu.utils.check_button_click(fix_rect, self.menu.mouse_clicked, self.menu.mouse_pos) and not self.menu.agent_running:
                    self.menu.on_agent_fix_click()

        # Back Button
        back_rect = self.menu.utils.draw_button("Back to Main Menu", main_x_center - 150, 820, 300, 50,
                                    self.menu.utils.check_button_hover(main_x_center - 150, 820, 300, 50, self.menu.mouse_pos))
        if self.menu.utils.check_button_click(back_rect, self.menu.mouse_clicked, self.menu.mouse_pos) and not self.menu.agent_running:
            self.menu.on_agent_back_click()

        # Show error messages at the bottom
        if self.menu.error_message and pygame.time.get_ticks() - self.menu.error_message_time < 5000:
            self.menu.utils.draw_text(self.menu.error_message, main_x_center, 880, self.menu.small_font, color=(255, 100, 100), center=True)
