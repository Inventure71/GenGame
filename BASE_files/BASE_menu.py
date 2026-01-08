import os


# Set video driver BEFORE importing pygame
os.environ['SDL_VIDEODRIVER'] = 'cocoa'

import shutil
import threading
import pygame

import importlib
import time
import sys
import traceback

from server import GameServer
from BASE_files.network_client import NetworkClient, EntityManager, sync_game_files
from BASE_files.patch_manager import PatchManager, PatchInfo
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

def run_client(network_client: NetworkClient, player_id: str = ""):
    print("="*70)
    print(" "*20 + "GENGAME - MULTIPLAYER CLIENT")
    print("="*70)
    print("\n🎮 GAME FEATURES:")
    print("  ✓ Multiplayer: Connect to server for real-time battles")
    print("  ✓ Life System: Each player has 3 lives")
    print("  ✓ Respawn: Players respawn after death")
    print("  ✓ Weapon Pickups: Walk over weapons to pick them up!")
    print("  ✓ UI: Shows health, lives, and current weapon")
    print("  ✓ Winner: Last player standing wins!")
    print("\n🎯 CONTROLS:")
    print("  Arrow Keys / WASD: Move Player")
    print("  Mouse Left-Click: Primary Fire (if you have a weapon)")
    print("  Mouse Right-Click: Secondary Fire")
    print("  E/F: Special Fire")
    print("  Q: Drop current weapon")
    print("  ESC: Quit game")
    print("="*70)
    print(f"\nConnecting to server at {network_client.host}:{network_client.port}...\n")

    try:
        # Check if client is connected
        if not network_client or not network_client.connected:
            print("❌ Network client not connected! Cannot start game.")
            return

        # Initialize Pygame (safe to call multiple times)
        pygame.init()
        width, height = 1400, 900  # Match server arena dimensions
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption(f"GenGame Client - {player_id}")
        clock = pygame.time.Clock()
        print("⚠️  IMPORTANT: Click on the game window to enable keyboard input for movement!")

        # Initialize network client and entity manager
        entity_manager = EntityManager()

        # Set up network callbacks
        assigned_character = None

        def on_character_assigned(assignment):
            nonlocal assigned_character
            assigned_character = assignment.get('assigned_character')
            print(f"Assigned to control: {assigned_character}")

        def on_file_sync_received(files):
            print("Received file sync from server...")
            if sync_game_files(files):
                # Import the setup function from the synchronized GameFolder
                try:
                    import GameFolder.setup as game_setup
                    importlib.reload(game_setup)  # Ensure we get the latest version

                    # Import game-specific classes for modularity
                    nonlocal ui, Character
                    ui = game_setup.GameUI(screen, width, height)
                    Character = game_setup.Character

                    print("✓ Game files synchronized and classes loaded")
                    network_client.acknowledge_file_sync()

                except Exception as e:
                    print(f"Failed to load synchronized game: {e}")
                    network_client.disconnect()

        def on_game_state_received(game_state):
            entity_manager.update_from_server(game_state)

            # Set local player if not already set and we have character assignment
            if entity_manager.local_player_id is None and assigned_character:
                # Find character by assigned name
                for char_data in game_state.get('characters', []):
                    if char_data.get('name') == assigned_character:
                        entity_manager.set_local_player(char_data.get('network_id'))
                        # Initialize prediction with server position
                        server_pos = char_data.get('location', [0, 0])
                        entity_manager.prediction.predicted_position = server_pos.copy()
                        entity_manager.prediction.server_position = server_pos.copy()
                        break

            nonlocal game_over, winner
            game_over = game_state.get('game_over', False)
            winner = game_state.get('winner', None)

        def on_disconnected():
            print("Disconnected from server")
            nonlocal running
            running = False

        network_client.on_file_sync_received = on_file_sync_received
        network_client.on_game_state_received = on_game_state_received
        network_client.on_character_assigned = on_character_assigned
        network_client.on_disconnected = on_disconnected

        # Initialize local state
        game_over = False
        winner = None
        ui = None  # Will be created after file sync
        Character = None  # Will be loaded after file sync

        # Input state
        held_keys = set()
        mouse_pressed = [False, False, False]  # Left, Middle, Right
        special_fire_holding = False

        running = True
        last_input_time = 0.0

        print("Connected! Waiting for game to start...\n")

        # Request file synchronization from server
        network_client.request_file_sync()

        frame_count = 0
        while running:
            frame_count += 1
            frame_delta = clock.tick(60) / 1000.0
            current_time = time.time()

            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    held_keys.add(event.key)
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_q:
                        # Drop weapon
                        network_client.send_input({'drop_weapon': True}, entity_manager)
                elif event.type == pygame.KEYUP:
                    held_keys.discard(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button <= 3:
                        mouse_pressed[event.button - 1] = True
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button <= 3:
                        mouse_pressed[event.button - 1] = False

            # Get mouse position
            mx, my = pygame.mouse.get_pos()
            world_mx, world_my = mx, height - my  # Convert to world coordinates

            # Send input to server (throttled to reduce network traffic)
            if current_time - last_input_time > 0.016:  # ~60 FPS input rate
                input_data = {}
                
                # ALWAYS send mouse position for TronProjectile tracking
                input_data['mouse_pos'] = [world_mx, world_my]

                # Movement input - always send to ensure server updates character state
                direction = [0, 0]
                if pygame.K_LEFT in held_keys or pygame.K_a in held_keys:
                    direction[0] = -1
                if pygame.K_RIGHT in held_keys or pygame.K_d in held_keys:
                    direction[0] = 1
                if pygame.K_UP in held_keys or pygame.K_w in held_keys:
                    direction[1] = 1
                if pygame.K_DOWN in held_keys or pygame.K_s in held_keys:
                    direction[1] = -1

                # Always send movement input, even [0, 0], to update character state on server
                input_data['movement'] = direction

                # Shooting inputs
                if mouse_pressed[0]:  # Left click
                    input_data['shoot'] = [world_mx, world_my]
                if mouse_pressed[2]:  # Right click
                    input_data['secondary_fire'] = [world_mx, world_my]

                # Special fire (E or F key)
                if pygame.K_e in held_keys or pygame.K_f in held_keys:
                    input_data['special_fire'] = [world_mx, world_my]
                    input_data['special_fire_holding'] = True
                    special_fire_holding = True
                elif special_fire_holding:
                    # Send release
                    input_data['special_fire'] = [world_mx, world_my]
                    input_data['special_fire_holding'] = False
                    special_fire_holding = False

                # Always send input (at least mouse position)
                network_client.send_input(input_data, entity_manager)

                last_input_time = current_time

            # Update network client
            network_client.update()

            # Render
            screen.fill((135, 206, 235))  # Sky blue background

            # Draw all platforms and entities managed by the entity manager
            entity_manager.draw_all(screen, height)

            # Draw UI
            if Character and ui:
                characters = entity_manager.get_entities_by_type(Character)
                ui.draw(characters, game_over, winner, {})

            pygame.display.flip()

        # Cleanup
        network_client.disconnect()
        # Don't quit pygame here - let the menu handle it

    except Exception as e:
        print("\n" + "!"*70)
        print("CRITICAL ERROR: The client crashed!")
        print(f"Exception: {e}")
        print("!"*70)
        traceback.print_exc()
        print("!"*70)
        sys.exit(1)

class BaseMenu:
    def __init__(self):
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
        self.current_menu = "main"  # main, create_room, join_room, library, room, agent
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

        # Button properties
        self.button_color = (70, 70, 100)
        self.button_hover_color = (100, 100, 130)
        self.button_text_color = (255, 255, 255)
        self.button_width = 300
        self.button_height = 60

        # Mouse state
        self.mouse_pos = (0, 0)
        self.mouse_clicked = False
        self.frame_count = 0

        # Game state
        self.player_id = ""
        self.player_id_focused = False
        self.in_room = False
        self.room_code = ""
        self.available_games = []
        self.patch_to_apply = None

        # Agent menu state
        self.agent_prompt = ""
        self.agent_prompt_focused = False
        self.agent_running = False
        self.agent_results = None
        self.show_fix_prompt = False

        # Patch saving state
        self.patch_name = ""
        self.patch_name_focused = False
        self.patch_cursor_pos = 0
        self.patch_selection_start = 0
        self.patch_selection_end = 0
        self.patch_scroll_offset = 0

        # Text input state for agent prompt
        self.agent_cursor_pos = 0
        self.agent_selection_start = 0
        self.agent_selection_end = 0
        self.agent_scroll_offset = 0

        self.client = None
        self.server_thread = None
        self.server_instance = None  # Store server instance for shutdown
        self.server_host = "127.0.0.1"
        self.server_port = 5555
        
        # Patch manager
        self.patch_manager = PatchManager()
        self.patches_ready = False  # Track if player marked patches as ready
        self.scroll_offset = 0  # For scrollable patch list
        self.max_visible_patches = 8  # Number of patches visible at once
        
        print("BaseMenu initialization complete.")

    def draw_button(self, text: str, x: int, y: int, width: int, height: int, hovered: bool = False) -> pygame.Rect:
        """Draw a button and return its rect for collision detection."""
        color = self.button_hover_color if hovered else self.button_color
        rect = pygame.Rect(x, y, width, height)

        # Draw button background
        pygame.draw.rect(self.screen, color, rect, border_radius=8)

        # Draw button border
        pygame.draw.rect(self.screen, (150, 150, 180), rect, 2, border_radius=8)

        # Draw text
        text_surf = self.button_font.render(text, True, self.button_text_color)
        text_rect = text_surf.get_rect(center=rect.center)
        self.screen.blit(text_surf, text_rect)

        return rect

    def draw_text(self, text: str, x: int, y: int, font=None, color=None, center=False):
        """Draw text on screen."""
        if font is None:
            font = self.button_font
        if color is None:
            color = self.menu_text_color

        text_surf = font.render(text, True, color)
        if center:
            text_rect = text_surf.get_rect(center=(x, y))
            self.screen.blit(text_surf, text_rect)
        else:
            self.screen.blit(text_surf, (x, y))

    def draw_text_field(self, text: str, x: int, y: int, width: int, height: int, focused: bool = False, placeholder: str = ""):
        """Draw a text input field."""
        # Draw field background
        field_color = (60, 60, 80) if focused else (40, 40, 50)
        pygame.draw.rect(self.screen, field_color, (x, y, width, height))
        pygame.draw.rect(self.screen, (100, 100, 120), (x, y, width, height), 2)  # Border

        # Draw text or placeholder
        display_text = text if text or not placeholder else placeholder
        text_color = self.menu_text_color if text else (150, 150, 150)

        # Render text and ensure it fits in the field
        text_surf = self.button_font.render(display_text, True, text_color)
        if text_surf.get_width() > width - 20:  # Leave some padding
            # Truncate text if too long
            while text_surf.get_width() > width - 20 and len(display_text) > 0:
                display_text = display_text[:-1]
                text_surf = self.button_font.render(display_text, True, text_color)

        # Draw the text
        text_y = y + (height - text_surf.get_height()) // 2
        self.screen.blit(text_surf, (x + 10, text_y))

        # Draw cursor if focused
        if focused:
            cursor_x = x + 10 + text_surf.get_width()
            cursor_y = text_y
            pygame.draw.line(self.screen, self.menu_text_color,
                           (cursor_x, cursor_y),
                           (cursor_x, cursor_y + text_surf.get_height()), 2)

        return pygame.Rect(x, y, width, height)

    def show_menu(self, menu_name: str):
        """Switch to a different menu."""
        self.current_menu = menu_name

    def check_button_click(self, button_rect: pygame.Rect) -> bool:
        """Check if a button was clicked."""
        return self.mouse_clicked and button_rect.collidepoint(self.mouse_pos)

    def render_main_menu(self):
        """Render the main menu."""
        self.screen.fill(self.menu_background_color)

        # Player ID text field at the top
        field_width = 300
        field_height = 40
        field_x = (1400 - field_width) // 2  # Center horizontally
        field_y = 20

        player_id_rect = self.draw_text_field(self.player_id, field_x, field_y, field_width, field_height,
                                             self.player_id_focused, "Enter Player ID")

        # Handle clicking on the text field
        if self.check_button_click(player_id_rect):
            self.player_id_focused = True
        elif self.mouse_clicked and not player_id_rect.collidepoint(self.mouse_pos):
            self.player_id_focused = False

        # Title
        self.draw_text("GEN GAME", 700, 120, self.menu_font, center=True)

        # Subtitle
        self.draw_text("Multiplayer Gaming Platform", 700, 180, self.small_font, center=True)

        # Buttons
        center_x = 700
        button_y = 250  # Moved down to make room for player ID field
        button_spacing = 80

        # Create Room Button
        create_rect = self.draw_button("Create Room", center_x - self.button_width//2, button_y,
                                      self.button_width, self.button_height,
                                      self.check_button_hover(center_x - self.button_width//2, button_y, self.button_width, self.button_height))
        if self.check_button_click(create_rect):
            self.on_create_room_click()

        # Join Room Button
        join_rect = self.draw_button("Join Room", center_x - self.button_width//2, button_y + button_spacing,
                                    self.button_width, self.button_height,
                                    self.check_button_hover(center_x - self.button_width//2, button_y + button_spacing, self.button_width, self.button_height))
        if self.check_button_click(join_rect):
            self.on_join_room_click()

        # Library Button
        library_rect = self.draw_button("Game Library", center_x - self.button_width//2, button_y + button_spacing * 2,
                                       self.button_width, self.button_height,
                                       self.check_button_hover(center_x - self.button_width//2, button_y + button_spacing * 2, self.button_width, self.button_height))
        if self.check_button_click(library_rect):
            self.on_library_click()

        # Agent Content Button
        agent_rect = self.draw_button("Agent Content", center_x - self.button_width//2, button_y + button_spacing * 3,
                                     self.button_width, self.button_height,
                                     self.check_button_hover(center_x - self.button_width//2, button_y + button_spacing * 3, self.button_width, self.button_height))
        if self.check_button_click(agent_rect):
            self.on_agent_content_click()

        # Settings Button
        settings_rect = self.draw_button("Settings", center_x - self.button_width//2, button_y + button_spacing * 4,
                                        self.button_width, self.button_height,
                                        self.check_button_hover(center_x - self.button_width//2, button_y + button_spacing * 4, self.button_width, self.button_height))
        if self.check_button_click(settings_rect):
            self.on_settings_click()

        # Quit Button
        quit_rect = self.draw_button("Quit", center_x - self.button_width//2, button_y + button_spacing * 5,
                                    self.button_width, self.button_height,
                                    self.check_button_hover(center_x - self.button_width//2, button_y + button_spacing * 5, self.button_width, self.button_height))
        if self.check_button_click(quit_rect):
            self.on_quit_click()

        # Show error message if any (for a few seconds)
        if self.error_message and pygame.time.get_ticks() - self.error_message_time < 5000:  # 5 seconds
            self.draw_text(self.error_message, 700, 550, self.small_font, color=(255, 100, 100), center=True)
        elif self.error_message:
            # Clear old error message
            self.error_message = None

    def render_room_menu(self):
        """Render the room menu with patch manager."""
        self.screen.fill(self.menu_background_color)

        # Try to connect if not already connected (happens when entering room)
        # For joining clients, this will establish the connection
        # For hosts, they should already be connected from create_room()
        if not self.client or not self.client.connected:
            connection_attempt_time = getattr(self, 'connection_attempt_time', 0)
            current_time = pygame.time.get_ticks()

            # Only attempt connection once every 2 seconds to avoid spam
            if current_time - connection_attempt_time > 2000:
                self.connection_attempt_time = current_time
                print("Attempting to connect to room...")
                if not self.connect_to_server():
                    # Connection failed - show error and return to main menu
                    self.show_error_message("Failed to connect to room - no server found")
                    self.show_menu("main")
                    return
        
        # Scan patches if not done yet
        if not self.patch_manager.available_patches:
            self.patch_manager.scan_patches()

        # Title
        self.draw_text("Game Room", 700, 40, self.menu_font, center=True)

        # Room status
        status_text = f"Status: {'Connected' if self.client and self.client.connected else 'Connecting...'}"
        self.draw_text(status_text, 700, 90, self.small_font, center=True)

        # === PATCH MANAGER UI ===
        patch_panel_x = 150
        patch_panel_y = 130
        patch_panel_width = 1100
        patch_panel_height = 450
        
        # Draw patch panel background
        pygame.draw.rect(self.screen, (30, 30, 40), 
                        (patch_panel_x, patch_panel_y, patch_panel_width, patch_panel_height))
        pygame.draw.rect(self.screen, (100, 100, 120), 
                        (patch_panel_x, patch_panel_y, patch_panel_width, patch_panel_height), 2)
        
        # Patch selection title
        self.draw_text(f"Select Patches (0-3) - {len(self.patch_manager.selected_patches)}/3 selected", 
                      patch_panel_x + 10, patch_panel_y + 10, self.button_font)
        
        # Scrollable patch list
        list_start_y = patch_panel_y + 50
        item_height = 45
        
        patches = self.patch_manager.available_patches
        visible_patches = patches[self.scroll_offset:self.scroll_offset + self.max_visible_patches]
        
        for i, patch in enumerate(visible_patches):
            actual_index = self.scroll_offset + i
            item_y = list_start_y + i * item_height
            
            # Draw patch item background
            item_color = (50, 100, 50) if patch.selected else (50, 50, 60)
            item_rect = pygame.Rect(patch_panel_x + 10, item_y, patch_panel_width - 20, item_height - 5)
            
            # Check if mouse hovering
            is_hovered = item_rect.collidepoint(self.mouse_pos)
            if is_hovered and not patch.selected:
                item_color = (70, 70, 80)
            
            pygame.draw.rect(self.screen, item_color, item_rect, border_radius=5)
            pygame.draw.rect(self.screen, (150, 150, 180), item_rect, 2, border_radius=5)
            
            # Check for click
            if self.check_button_click(item_rect):
                self.patch_manager.toggle_selection(actual_index)
            
            # Draw patch info
            checkbox = "[X]" if patch.selected else "[ ]"
            text = f"{checkbox} {patch.name} (Base: {patch.base_backup}, Changes: {patch.num_changes})"
            self.draw_text(text, patch_panel_x + 20, item_y + 12, self.small_font)
        
        # Scroll indicators
        if self.scroll_offset > 0:
            self.draw_text("▲ Scroll Up", patch_panel_x + patch_panel_width - 120, patch_panel_y + 10, 
                          self.small_font, color=(200, 200, 255))
        if self.scroll_offset + self.max_visible_patches < len(patches):
            self.draw_text("▼ Scroll Down", patch_panel_x + patch_panel_width - 120, 
                          patch_panel_y + patch_panel_height - 30, 
                          self.small_font, color=(200, 200, 255))
        
        # Show no patches message if empty
        if not patches:
            self.draw_text("No patches found in __patches directory", 
                          700, patch_panel_y + 200, self.button_font, center=True)

        # === BUTTONS ===
        center_x = 700
        button_y = 620
        button_spacing = 80

        # Ready/Start Game Button (only show if connected)
        if self.client and self.client.connected:
            ready_text = "Ready!" if self.patches_ready else "Mark as Ready"
            ready_color = self.button_hover_color if self.patches_ready else self.button_color
            
            ready_rect = pygame.Rect(center_x - self.button_width//2, button_y, 
                                    self.button_width, self.button_height)
            pygame.draw.rect(self.screen, ready_color, ready_rect, border_radius=8)
            pygame.draw.rect(self.screen, (150, 150, 180), ready_rect, 2, border_radius=8)
            
            text_surf = self.button_font.render(ready_text, True, self.button_text_color)
            text_rect = text_surf.get_rect(center=ready_rect.center)
            self.screen.blit(text_surf, text_rect)
            
            if self.check_button_click(ready_rect):
                self.on_ready_click()
            button_y += button_spacing

        # Leave Room Button
        leave_rect = self.draw_button("Leave Room", center_x - self.button_width//2, button_y,
                                     self.button_width, self.button_height,
                                     self.check_button_hover(center_x - self.button_width//2, button_y, self.button_width, self.button_height))
        if self.check_button_click(leave_rect):
            self.on_leave_room_click()

        # Back to Menu Button
        back_rect = self.draw_button("Back to Menu", center_x - self.button_width//2, button_y + button_spacing,
                                    self.button_width, self.button_height,
                                    self.check_button_hover(center_x - self.button_width//2, button_y + button_spacing, self.button_width, self.button_height))
        if self.check_button_click(back_rect):
            self.on_back_to_menu_click()

        # Show error message if any (for a few seconds)
        if self.error_message and pygame.time.get_ticks() - self.error_message_time < 5000:  # 5 seconds
            self.draw_text(self.error_message, 700, 850, self.small_font, color=(255, 100, 100), center=True)
        elif self.error_message:
            # Clear old error message
            self.error_message = None

    def render_library_menu(self):
        """Render the game library menu."""
        self.screen.fill(self.menu_background_color)

        # Title
        self.draw_text("Game Library", 700, 80, self.menu_font, center=True)

        # Placeholder content
        self.draw_text("Available Games:", 200, 150, self.button_font)
        self.draw_text("(Game library functionality - PLACEHOLDER)", 200, 200, self.small_font)

        # Back Button
        back_rect = self.draw_button("Back", 450, 500, 300, 60,
                                    self.check_button_hover(450, 500, 300, 60))
        if self.check_button_click(back_rect):
            self.on_library_back_click()

    def render_agent_menu(self):
        """Render the agent content creation menu."""
        self.screen.fill(self.menu_background_color)

        # Title
        self.draw_text("Agent Content Creation", 700, 30, self.menu_font, center=True)

        # Prompt text field
        prompt_y = 80
        prompt_width = 1000
        prompt_height = 250

        # Draw prompt label
        self.draw_text("Paste your content request:", 700, prompt_y - 30, self.button_font, center=True)

        # Draw prompt text field background
        prompt_rect = pygame.Rect(700 - prompt_width//2, prompt_y, prompt_width, prompt_height)
        pygame.draw.rect(self.screen, (40, 40, 50), prompt_rect)
        pygame.draw.rect(self.screen, (100, 100, 120), prompt_rect, 2)

        # Handle clicking on the prompt field
        if self.check_button_click(prompt_rect) and not self.agent_running:
            self.agent_prompt_focused = True
            # Calculate cursor position from mouse click
            self.update_cursor_from_mouse_click(prompt_rect, prompt_y)
        elif self.mouse_clicked and not prompt_rect.collidepoint(self.mouse_pos):
            self.agent_prompt_focused = False

        # Draw focus border
        if self.agent_prompt_focused:
            pygame.draw.rect(self.screen, (150, 150, 180), prompt_rect, 3)

        # Draw prompt text with selection and cursor
        self.draw_text_input(prompt_rect, prompt_y, prompt_width, prompt_height)

        # Webserver URL display
        url_y = prompt_y + prompt_height + 15
        self.draw_text("Agent Monitor: http://127.0.0.1:8765", 700, url_y, self.small_font, center=True)

        # Paste and Send buttons
        send_y = url_y + 35

        # Paste Clipboard button
        paste_button_width = 100
        paste_rect = self.draw_button("Paste", 700 - self.button_width//2 - paste_button_width - 20, send_y,
                                     paste_button_width, self.button_height,
                                     self.check_button_hover(700 - self.button_width//2 - paste_button_width - 20, send_y, paste_button_width, self.button_height))
        if self.check_button_click(paste_rect) and not self.agent_running:
            self.paste_clipboard()

        # Send button
        send_button_text = "Running Agent..." if self.agent_running else "Send to Agent"
        send_rect = self.draw_button(send_button_text, 700 - self.button_width//2, send_y,
                                    self.button_width, self.button_height,
                                    self.check_button_hover(700 - self.button_width//2, send_y, self.button_width, self.button_height))
        if self.check_button_click(send_rect) and not self.agent_running and self.agent_prompt.strip():
            self.on_agent_send_click()

        # Results display
        current_y = send_y + self.button_height + 40
        if self.agent_results:
            self.draw_text(f"Test Results: {self.agent_results['passed']}/{self.agent_results['total']} passed",
                          700, current_y, self.button_font, center=True)
            current_y += 50

            # Fix button (only show if there were failures)
            if self.agent_results['passed'] < self.agent_results['total']:
                fix_rect = self.draw_button("Fix Issues?", 700 - self.button_width//2, current_y,
                                           self.button_width, self.button_height,
                                           self.check_button_hover(700 - self.button_width//2, current_y, self.button_width, self.button_height))
                if self.check_button_click(fix_rect):
                    self.on_agent_fix_click()
                current_y += self.button_height + 30

            # Patch saving section
            # Draw label
            self.draw_text("Patch Name:", 700, current_y, self.button_font, center=True)
            current_y += 35

            # Patch name input field
            patch_name_width = 400
            patch_name_height = 40
            patch_name_rect = pygame.Rect(700 - patch_name_width//2, current_y, patch_name_width, patch_name_height)
            pygame.draw.rect(self.screen, (40, 40, 50), patch_name_rect)
            pygame.draw.rect(self.screen, (100, 100, 120), patch_name_rect, 2)

            # Handle clicking on patch name field
            if self.check_button_click(patch_name_rect) and not self.agent_running:
                self.patch_name_focused = True
                self.agent_prompt_focused = False
                self.update_patch_cursor_from_mouse_click(patch_name_rect, current_y)
            elif self.mouse_clicked and not patch_name_rect.collidepoint(self.mouse_pos):
                self.patch_name_focused = False

            # Draw focus border
            if self.patch_name_focused:
                pygame.draw.rect(self.screen, (150, 150, 180), patch_name_rect, 3)

            # Draw patch name text
            self.draw_patch_text_input(patch_name_rect, current_y, patch_name_width, patch_name_height)
            current_y += patch_name_height + 15

            # Save patch button
            save_patch_rect = self.draw_button("Save to Patch", 700 - self.button_width//2, current_y,
                                             self.button_width, self.button_height,
                                             self.check_button_hover(700 - self.button_width//2, current_y, self.button_width, self.button_height))
            if self.check_button_click(save_patch_rect) and not self.agent_running and self.patch_name.strip():
                self.on_agent_save_patch_click()

        # Back button at the bottom
        back_y = 820
        back_rect = self.draw_button("Back to Menu", 700 - self.button_width//2, back_y,
                                    self.button_width, self.button_height,
                                    self.check_button_hover(700 - self.button_width//2, back_y, self.button_width, self.button_height))
        if self.check_button_click(back_rect) and not self.agent_running:
            self.on_agent_back_click()

        # Handle text input for prompt field
        if self.agent_prompt_focused:
            self.handle_agent_text_input()

        # Handle text input for patch name field
        if self.patch_name_focused:
            self.handle_patch_text_input()

    def check_button_hover(self, x: int, y: int, width: int, height: int) -> bool:
        """Check if mouse is hovering over a button."""
        button_rect = pygame.Rect(x, y, width, height)
        return button_rect.collidepoint(self.mouse_pos)

    def render(self):
        """Render the current menu."""
        self.frame_count += 1

        if self.current_menu == "main":
            self.render_main_menu()
        elif self.current_menu == "room":
            self.render_room_menu()
        elif self.current_menu == "library":
            self.render_library_menu()
        elif self.current_menu == "agent":
            self.render_agent_menu()

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

        # Handle agent prompt input
        elif self.current_menu == "agent" and self.agent_prompt_focused and not self.agent_running:
            mods = pygame.key.get_mods()

            if event.key == pygame.K_RETURN:
                # Insert newline with Enter
                self.insert_text('\n')
            elif event.key == pygame.K_BACKSPACE:
                if self.has_selection():
                    self.delete_selection()
                elif self.agent_cursor_pos > 0:
                    # Delete character before cursor
                    self.agent_prompt = self.agent_prompt[:self.agent_cursor_pos-1] + self.agent_prompt[self.agent_cursor_pos:]
                    self.agent_cursor_pos -= 1
                    self.agent_selection_start = self.agent_cursor_pos
                    self.agent_selection_end = self.agent_cursor_pos
            elif event.key == pygame.K_DELETE:
                if self.has_selection():
                    self.delete_selection()
                elif self.agent_cursor_pos < len(self.agent_prompt):
                    # Delete character after cursor
                    self.agent_prompt = self.agent_prompt[:self.agent_cursor_pos] + self.agent_prompt[self.agent_cursor_pos+1:]
            elif event.key == pygame.K_LEFT:
                if mods & pygame.KMOD_SHIFT:
                    # Extend selection
                    if self.agent_cursor_pos > 0:
                        self.agent_cursor_pos -= 1
                        if self.agent_cursor_pos < self.agent_selection_start:
                            self.agent_selection_start = self.agent_cursor_pos
                        else:
                            self.agent_selection_end = self.agent_cursor_pos
                else:
                    # Move cursor
                    if self.has_selection():
                        self.agent_cursor_pos = min(self.agent_selection_start, self.agent_selection_end)
                        self.agent_selection_start = self.agent_cursor_pos
                        self.agent_selection_end = self.agent_cursor_pos
                    elif self.agent_cursor_pos > 0:
                        self.agent_cursor_pos -= 1
            elif event.key == pygame.K_RIGHT:
                if mods & pygame.KMOD_SHIFT:
                    # Extend selection
                    if self.agent_cursor_pos < len(self.agent_prompt):
                        self.agent_cursor_pos += 1
                        if self.agent_cursor_pos > self.agent_selection_end:
                            self.agent_selection_end = self.agent_cursor_pos
                        else:
                            self.agent_selection_start = self.agent_cursor_pos
                else:
                    # Move cursor
                    if self.has_selection():
                        self.agent_cursor_pos = max(self.agent_selection_start, self.agent_selection_end)
                        self.agent_selection_start = self.agent_cursor_pos
                        self.agent_selection_end = self.agent_cursor_pos
                    elif self.agent_cursor_pos < len(self.agent_prompt):
                        self.agent_cursor_pos += 1
            elif event.key == pygame.K_UP:
                # Move to previous line
                line, col = self.get_line_col(self.agent_cursor_pos)
                if line > 0:
                    new_pos = self.get_pos_from_line_col(line - 1, col)
                    if mods & pygame.KMOD_SHIFT:
                        self.agent_cursor_pos = new_pos
                        if new_pos < self.agent_selection_start:
                            self.agent_selection_start = new_pos
                        else:
                            self.agent_selection_end = new_pos
                    else:
                        self.agent_cursor_pos = new_pos
                        self.agent_selection_start = new_pos
                        self.agent_selection_end = new_pos
            elif event.key == pygame.K_DOWN:
                # Move to next line
                line, col = self.get_line_col(self.agent_cursor_pos)
                lines = self.agent_prompt.split('\n')
                if line < len(lines) - 1:
                    new_pos = self.get_pos_from_line_col(line + 1, col)
                    if mods & pygame.KMOD_SHIFT:
                        self.agent_cursor_pos = new_pos
                        if new_pos > self.agent_selection_end:
                            self.agent_selection_end = new_pos
                        else:
                            self.agent_selection_start = new_pos
                    else:
                        self.agent_cursor_pos = new_pos
                        self.agent_selection_start = new_pos
                        self.agent_selection_end = new_pos
            elif event.key == pygame.K_HOME:
                # Move to start of line
                line, col = self.get_line_col(self.agent_cursor_pos)
                new_pos = self.get_pos_from_line_col(line, 0)
                if mods & pygame.KMOD_SHIFT:
                    self.agent_cursor_pos = new_pos
                    if new_pos < self.agent_selection_start:
                        self.agent_selection_start = new_pos
                    else:
                        self.agent_selection_end = new_pos
                else:
                    self.agent_cursor_pos = new_pos
                    self.agent_selection_start = new_pos
                    self.agent_selection_end = new_pos
            elif event.key == pygame.K_END:
                # Move to end of line
                line, col = self.get_line_col(self.agent_cursor_pos)
                lines = self.agent_prompt.split('\n')
                if line < len(lines):
                    new_pos = self.get_pos_from_line_col(line, len(lines[line]))
                    if mods & pygame.KMOD_SHIFT:
                        self.agent_cursor_pos = new_pos
                        if new_pos > self.agent_selection_end:
                            self.agent_selection_end = new_pos
                        else:
                            self.agent_selection_start = new_pos
                    else:
                        self.agent_cursor_pos = new_pos
                        self.agent_selection_start = new_pos
                        self.agent_selection_end = new_pos
            elif event.key == pygame.K_PAGEUP:
                # Scroll up
                self.agent_scroll_offset = max(0, self.agent_scroll_offset - 5)
            elif event.key == pygame.K_PAGEDOWN:
                # Scroll down
                max_chars_per_line = 1000 // 8  # Approximate
                display_lines = self.wrap_text_for_display(max_chars_per_line)
                visible_lines = 300 // 25  # Approximate
                max_scroll = max(0, len(display_lines) - visible_lines)
                self.agent_scroll_offset = min(max_scroll, self.agent_scroll_offset + 5)
            elif (mods & pygame.KMOD_CTRL) and event.key == pygame.K_a:
                # Select all
                self.select_all()
            elif (mods & pygame.KMOD_CTRL) and event.key == pygame.K_v:
                # Paste
                try:
                    clipboard_text = pygame.scrap.get(pygame.SCRAP_TEXT).decode('utf-8')
                    # Remove null bytes and normalize line endings
                    clipboard_text = clipboard_text.replace('\x00', '').replace('\r\n', '\n').replace('\r', '\n')
                    self.insert_text(clipboard_text)
                except:
                    pass  # Clipboard not available or empty
            elif (mods & pygame.KMOD_CTRL) and event.key == pygame.K_c:
                # Copy
                if self.has_selection():
                    try:
                        selected_text = self.get_selected_text()
                        pygame.scrap.put(pygame.SCRAP_TEXT, selected_text.encode('utf-8'))
                    except:
                        pass  # Clipboard not available
            elif (mods & pygame.KMOD_CTRL) and event.key == pygame.K_x:
                # Cut
                if self.has_selection():
                    try:
                        selected_text = self.get_selected_text()
                        pygame.scrap.put(pygame.SCRAP_TEXT, selected_text.encode('utf-8'))
                        self.delete_selection()
                    except:
                        pass  # Clipboard not available
            elif event.key == pygame.K_ESCAPE:
                self.agent_prompt_focused = False
            else:
                # Add printable characters
                if event.unicode and event.unicode.isprintable():
                    self.insert_text(event.unicode)

        # Handle patch name input
        elif self.current_menu == "agent" and self.patch_name_focused and not self.agent_running:
            if event.key == pygame.K_RETURN:
                # Confirm patch name and save
                self.patch_name_focused = False
                if self.patch_name.strip():
                    self.on_agent_save_patch_click()
            elif event.key == pygame.K_BACKSPACE:
                if len(self.patch_name) > 0:
                    self.patch_name = self.patch_name[:-1]
                    self.patch_cursor_pos = len(self.patch_name)
                    self.patch_selection_start = self.patch_cursor_pos
                    self.patch_selection_end = self.patch_cursor_pos
            elif event.key == pygame.K_ESCAPE:
                self.patch_name_focused = False
            else:
                # Add printable characters
                if event.unicode and event.unicode.isprintable():
                    self.patch_name += event.unicode
                    self.patch_cursor_pos = len(self.patch_name)
                    self.patch_selection_start = self.patch_cursor_pos
                    self.patch_selection_end = self.patch_cursor_pos

        # Handle scrolling in room menu
        elif self.current_menu == "room":
            if event.key == pygame.K_UP:
                self.scroll_offset = max(0, self.scroll_offset - 1)
            elif event.key == pygame.K_DOWN:
                max_offset = max(0, len(self.patch_manager.available_patches) - self.max_visible_patches)
                self.scroll_offset = min(max_offset, self.scroll_offset + 1)

    # Placeholder methods for menu actions
    def on_create_room_click(self):
        """Handle create room button click."""
        if not self.player_id.strip():
            print("Error: Please enter a Player ID before creating a room")
            return
        print("Create Room clicked")
        self.create_room()  # This will start the server and connect as host
        self.show_menu("room")

    def on_join_room_click(self):
        """Handle join room button click."""
        if not self.player_id.strip():
            print("Error: Please enter a Player ID before joining a room")
            return
        print("Join Room clicked - entering room")
        # Connection will happen automatically when room menu is shown
        self.show_menu("room")

    def on_library_click(self):
        """Handle library button click."""
        print("Library clicked")
        self.show_menu("library")

    def on_agent_content_click(self):
        """Handle agent content button click."""
        print("Agent Content clicked")
        self.show_menu("agent")

    def on_settings_click(self):
        """Handle settings button click."""
        print("Settings clicked")
        # TODO: Show settings menu

    def on_quit_click(self):
        """Handle quit button click."""
        print("Quit clicked")
        self.running = False

    def on_ready_click(self):
        """Handle ready button click - sends patches to server."""
        print("Ready clicked - sending patches to server")
        if self.client and self.client.connected:
            # Mark as ready
            self.patches_ready = True
            
            # Get selected patches info
            selected_patches = self.patch_manager.get_selected_patches_info()
            
            # Send patches to server
            self.client.send_patches_selection(selected_patches)
            
            print(f"Sent {len(selected_patches)} patch(es) to server")
        else:
            print("Not connected to server!")
    

    def on_leave_room_click(self):
        """Handle leave room button click."""
        print("Leave Room clicked")
        self.show_menu("main")

    def on_back_to_menu_click(self):
        """Handle back to menu button click."""
        print("Back to Menu clicked")

        # Disconnect client first
        if self.client and self.client.connected:
            self.client.disconnect()

        # If this client is hosting the server, shut it down when leaving
        if self.server_instance and self.server_thread and self.server_thread.is_alive():
            print("Shutting down server (you were the host)...")
            # Stop the server cleanly
            self.server_instance.stop()
            # Wait for server thread to finish
            self.server_thread.join(timeout=2.0)
            self.server_instance = None
            self.server_thread = None

        self.show_menu("main")

    def on_library_back_click(self):
        """Handle library back button click."""
        print("Library Back clicked")
        self.show_menu("main")

    def on_agent_send_click(self):
        """Handle agent send button click."""
        print("Agent Send clicked")

        # Focus the text field if prompt is empty
        if not self.agent_prompt.strip():
            self.agent_prompt_focused = True
            return

        self.agent_running = True
        self.agent_results = None
        self.show_fix_prompt = False
        # Unfocus text fields
        self.agent_prompt_focused = False
        self.patch_name_focused = False

        # Run agent in a separate thread to avoid blocking the UI
        import threading
        agent_thread = threading.Thread(target=self.run_agent, args=(self.agent_prompt,))
        agent_thread.start()

    def on_agent_fix_click(self):
        """Handle agent fix button click."""
        print("Agent Fix clicked")
        self.agent_running = True
        self.show_fix_prompt = False
        # Unfocus text fields
        self.agent_prompt_focused = False
        self.patch_name_focused = False

        # Run agent fix in a separate thread
        import threading
        agent_thread = threading.Thread(target=self.run_agent_fix, args=(self.agent_results,))
        agent_thread.start()

    def on_agent_save_patch_click(self):
        """Handle agent save patch button click."""
        print(f"Agent Save Patch clicked: {self.patch_name}")

        # Save the current changes as a patch
        import os
        from coding.non_callable_tools.action_logger import action_logger

        # Create patches directory if it doesn't exist
        patches_dir = "__patches"
        if not os.path.exists(patches_dir):
            os.makedirs(patches_dir)

        # Save the patch
        patch_path = os.path.join(patches_dir, f"{self.patch_name}.json")
        success = action_logger.save_changes_to_extension_file(patch_path, name_of_backup="GameFolder")

        if success:
            print(f"✓ Patch saved successfully: {patch_path}")
            # Clear the patch name field
            self.patch_name = ""
            self.patch_name_focused = False
        else:
            print("✗ Failed to save patch")

    def on_agent_back_click(self):
        """Handle agent back button click."""
        print("Agent Back clicked")
        # Reset agent state
        self.agent_prompt = ""
        self.agent_prompt_focused = False
        self.agent_running = False
        self.agent_results = None
        # Reset patch state
        self.patch_name = ""
        self.patch_name_focused = False
        self.patch_cursor_pos = 0
        self.patch_selection_start = 0
        self.patch_selection_end = 0
        self.patch_scroll_offset = 0
        self.show_fix_prompt = False
        self.agent_cursor_pos = 0
        self.agent_selection_start = 0
        self.agent_selection_end = 0
        self.agent_scroll_offset = 0
        self.show_menu("main")

    def handle_agent_text_input(self):
        """Handle text input for the agent prompt field."""
        # This will be called from render_agent_menu when the field is focused
        pass  # Text input is handled in the main event loop

    def draw_text_input(self, rect, y, width, height):
        """Draw the text input field with word wrapping, scrolling, cursor and selection."""
        line_height = 25
        char_width = 8
        padding = 10
        max_chars_per_line = (width - 2 * padding) // char_width
        visible_lines = (height - 2 * padding) // line_height

        # Wrap text into display lines
        display_lines = self.wrap_text_for_display(max_chars_per_line)

        # Calculate scrolling
        cursor_line_idx = self.get_display_line_from_cursor(display_lines)
        if cursor_line_idx < self.agent_scroll_offset:
            self.agent_scroll_offset = cursor_line_idx
        elif cursor_line_idx >= self.agent_scroll_offset + visible_lines:
            self.agent_scroll_offset = cursor_line_idx - visible_lines + 1

        # Ensure scroll offset is valid
        max_scroll = max(0, len(display_lines) - visible_lines)
        self.agent_scroll_offset = max(0, min(self.agent_scroll_offset, max_scroll))

        # Draw visible lines
        for i in range(visible_lines):
            line_idx = self.agent_scroll_offset + i
            if line_idx >= len(display_lines):
                break

            line_y = y + padding + i * line_height
            display_line = display_lines[line_idx]

            # Draw selection background if there's a selection
            if self.has_selection():
                sel_ranges = self.get_selection_ranges_for_display_line(display_lines, line_idx)
                for start_col, end_col in sel_ranges:
                    if start_col < end_col:
                        sel_x = rect.left + padding + start_col * char_width
                        sel_width = (end_col - start_col) * char_width
                        pygame.draw.rect(self.screen, (100, 150, 200),
                                       (sel_x, line_y, sel_width, line_height))

            # Draw the line text
            self.draw_text(display_line, rect.left + padding, line_y, self.small_font)

            # Draw cursor if focused and on this line
            if self.agent_prompt_focused and self.frame_count % 60 < 30:  # Blinking cursor
                cursor_display_line, cursor_col = self.get_cursor_display_position(display_lines)
                if cursor_display_line == line_idx:
                    cursor_x = rect.left + padding + cursor_col * char_width
                    pygame.draw.line(self.screen, self.menu_text_color,
                                   (cursor_x, line_y),
                                   (cursor_x, line_y + line_height), 2)

        # Draw scroll indicators
        if self.agent_scroll_offset > 0:
            self.draw_text("▲", rect.right - 20, y + padding, self.small_font, color=(200, 200, 255))
        if self.agent_scroll_offset + visible_lines < len(display_lines):
            self.draw_text("▼", rect.right - 20, y + height - padding - line_height, self.small_font, color=(200, 200, 255))

    def has_selection(self):
        """Check if there's text selected."""
        return self.agent_selection_start != self.agent_selection_end

    def get_line_col(self, pos):
        """Convert absolute position to line and column."""
        lines = self.agent_prompt.split('\n')
        current_pos = 0

        for line_idx, line in enumerate(lines):
            line_length = len(line) + 1  # +1 for newline
            if current_pos + line_length > pos:
                col = pos - current_pos
                return line_idx, col
            current_pos += line_length

        # End of text
        return len(lines) - 1, len(lines[-1])

    def get_pos_from_line_col(self, line, col):
        """Convert line and column to absolute position."""
        lines = self.agent_prompt.split('\n')
        pos = 0

        for i in range(min(line, len(lines))):
            pos += len(lines[i]) + 1  # +1 for newline

        pos += min(col, len(lines[line]) if line < len(lines) else 0)
        return pos

    def update_cursor_from_mouse_click(self, rect, y):
        """Update cursor position based on mouse click in wrapped text."""
        line_height = 25
        char_width = 8
        padding = 10
        max_chars_per_line = (rect.width - 2 * padding) // char_width

        # Calculate which display line was clicked
        click_y = self.mouse_pos[1] - y - padding
        clicked_display_line = max(0, min(int(click_y // line_height), 10))  # Assume up to 10 visible lines

        # Add scroll offset
        actual_display_line = clicked_display_line + self.agent_scroll_offset

        # Calculate which column was clicked
        click_x = self.mouse_pos[0] - rect.left - padding
        clicked_col = max(0, int(click_x // char_width))

        # Get display lines to find the actual cursor position
        display_lines = self.wrap_text_for_display(max_chars_per_line)

        if actual_display_line < len(display_lines):
            display_line = display_lines[actual_display_line]
            clicked_col = min(clicked_col, len(display_line))

            # Convert display position back to actual text position
            self.agent_cursor_pos = self.get_text_pos_from_display_pos(display_lines, actual_display_line, clicked_col)
        else:
            # Clicked beyond the text
            self.agent_cursor_pos = len(self.agent_prompt)

        self.agent_selection_start = self.agent_cursor_pos
        self.agent_selection_end = self.agent_cursor_pos

    def delete_selection(self):
        """Delete the selected text."""
        if not self.has_selection():
            return

        start = min(self.agent_selection_start, self.agent_selection_end)
        end = max(self.agent_selection_start, self.agent_selection_end)

        self.agent_prompt = self.agent_prompt[:start] + self.agent_prompt[end:]
        self.agent_cursor_pos = start
        self.agent_selection_start = start
        self.agent_selection_end = start

    def get_selected_text(self):
        """Get the currently selected text."""
        if not self.has_selection():
            return ""

        start = min(self.agent_selection_start, self.agent_selection_end)
        end = max(self.agent_selection_start, self.agent_selection_end)
        return self.agent_prompt[start:end]

    def insert_text(self, text):
        """Insert text at cursor position."""
        # Delete selection first if any
        if self.has_selection():
            self.delete_selection()

        self.agent_prompt = self.agent_prompt[:self.agent_cursor_pos] + text + self.agent_prompt[self.agent_cursor_pos:]
        self.agent_cursor_pos += len(text)
        self.agent_selection_start = self.agent_cursor_pos
        self.agent_selection_end = self.agent_cursor_pos

    def select_all(self):
        """Select all text."""
        self.agent_selection_start = 0
        self.agent_selection_end = len(self.agent_prompt)
        self.agent_cursor_pos = len(self.agent_prompt)

    def wrap_text_for_display(self, max_chars_per_line):
        """Wrap text to fit within max_chars_per_line and return display lines."""
        if not self.agent_prompt:
            return [""]

        display_lines = []
        paragraphs = self.agent_prompt.split('\n')

        for paragraph in paragraphs:
            if not paragraph:
                display_lines.append("")
                continue

            words = paragraph.split(' ')
            current_line = ""

            for word in words:
                # Check if adding this word would exceed the line length
                if current_line and len(current_line + ' ' + word) <= max_chars_per_line:
                    current_line += ' ' + word
                elif len(word) <= max_chars_per_line:
                    # Start new line with this word
                    if current_line:
                        display_lines.append(current_line)
                    current_line = word
                else:
                    # Word is too long, split it
                    if current_line:
                        display_lines.append(current_line)
                        current_line = ""
                    # Split long word
                    for i in range(0, len(word), max_chars_per_line):
                        display_lines.append(word[i:i + max_chars_per_line])

            if current_line:
                display_lines.append(current_line)

        return display_lines if display_lines else [""]

    def get_display_line_from_cursor(self, display_lines):
        """Get the display line index where the cursor is located."""
        cursor_pos = self.agent_cursor_pos
        char_count = 0

        for line_idx, line in enumerate(display_lines):
            line_length = len(line) + 1  # +1 for space/newline
            if char_count + line_length > cursor_pos:
                return line_idx
            char_count += line_length

        return len(display_lines) - 1

    def get_cursor_display_position(self, display_lines):
        """Get the cursor position in display coordinates (line, column)."""
        cursor_pos = self.agent_cursor_pos
        char_count = 0

        for line_idx, line in enumerate(display_lines):
            line_length = len(line) + 1  # +1 for space/newline
            if char_count + line_length > cursor_pos:
                col = cursor_pos - char_count
                return line_idx, min(col, len(line))
            char_count += line_length

        # End of text
        last_line_idx = len(display_lines) - 1
        return last_line_idx, len(display_lines[last_line_idx]) if display_lines else 0

    def get_selection_ranges_for_display_line(self, display_lines, display_line_idx):
        """Get selection ranges for a specific display line."""
        if not self.has_selection():
            return []

        sel_start = min(self.agent_selection_start, self.agent_selection_end)
        sel_end = max(self.agent_selection_start, self.agent_selection_end)

        # Find the character ranges for this display line
        char_start = 0
        for i in range(display_line_idx):
            char_start += len(display_lines[i]) + 1

        char_end = char_start + len(display_lines[display_line_idx])

        # Check if selection intersects with this line
        line_sel_start = max(sel_start, char_start)
        line_sel_end = min(sel_end, char_end)

        if line_sel_start < line_sel_end:
            start_col = line_sel_start - char_start
            end_col = line_sel_end - char_start
            return [(start_col, end_col)]

        return []

    def get_text_pos_from_display_pos(self, display_lines, display_line_idx, display_col):
        """Convert display position back to actual text position."""
        pos = 0

        for i in range(display_line_idx):
            if i < len(display_lines):
                # Add the length of this display line plus space/newline
                pos += len(display_lines[i]) + 1

        # Add the column position within the current display line
        if display_line_idx < len(display_lines):
            pos += min(display_col, len(display_lines[display_line_idx]))

        return min(pos, len(self.agent_prompt))

    # =========================================================================
    # PATCH NAME TEXT INPUT METHODS
    # =========================================================================

    def handle_patch_text_input(self):
        """Handle text input for the patch name field (simplified single-line version)."""
        pass  # Text input is handled in the main event loop

    def update_patch_cursor_from_mouse_click(self, rect, y):
        """Update cursor position based on mouse click in patch name field."""
        if not rect.collidepoint(self.mouse_pos):
            return

        # Calculate relative x position
        relative_x = self.mouse_pos[0] - rect.left - 10  # 10 is padding
        char_width = 8

        # Calculate character position
        char_pos = relative_x // char_width
        self.patch_cursor_pos = max(0, min(char_pos, len(self.patch_name)))
        self.patch_selection_start = self.patch_cursor_pos
        self.patch_selection_end = self.patch_cursor_pos

    def draw_patch_text_input(self, rect, y, width, height):
        """Draw the patch name text input field (simplified single-line version)."""
        padding = 10
        char_width = 8
        line_height = 25

        # Draw the text
        text_x = rect.left + padding
        text_y = y + (height - line_height) // 2 + 5
        display_text = self.patch_name

        # Draw selection background if there's a selection
        if self.patch_selection_start != self.patch_selection_end:
            sel_start = min(self.patch_selection_start, self.patch_selection_end)
            sel_end = max(self.patch_selection_start, self.patch_selection_end)
            sel_x = text_x + sel_start * char_width
            sel_width = (sel_end - sel_start) * char_width
            pygame.draw.rect(self.screen, (100, 150, 200),
                           (sel_x, text_y - 2, sel_width, line_height))

        # Draw the text
        self.draw_text(display_text, text_x, text_y, self.small_font)

        # Draw cursor if focused
        if self.patch_name_focused:
            cursor_x = text_x + self.patch_cursor_pos * char_width
            pygame.draw.line(self.screen, (255, 255, 255),
                           (cursor_x, text_y - 2), (cursor_x, text_y + line_height - 2), 2)

    def paste_clipboard(self):
        """Paste clipboard content into the agent prompt."""
        import platform
        system = platform.system().lower()

        # Try platform-specific clipboard first
        try:
            if system == "darwin":  # macOS
                import subprocess
                result = subprocess.run(['pbpaste'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout:
                    clipboard_text = result.stdout
                    # Normalize line endings
                    clipboard_text = clipboard_text.replace('\r\n', '\n').replace('\r', '\n')
                    self.insert_text(clipboard_text)
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
                            self.insert_text(clipboard_text)
                            print(f"Pasted {len(clipboard_text)} characters from clipboard")
                            return
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        continue

            elif system == "windows":
                import subprocess
                result = subprocess.run(['powershell', 'Get-Clipboard'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout:
                    clipboard_text = result.stdout
                    # Normalize line endings
                    clipboard_text = clipboard_text.replace('\r\n', '\n').replace('\r', '\n')
                    self.insert_text(clipboard_text)
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
                self.insert_text(clipboard_text)
                print(f"Pasted {len(clipboard_text)} characters from clipboard (pygame)")
                return

        except Exception as e:
            pass

        print("Failed to paste from clipboard - try copying text first")
        print("Supported platforms: macOS, Linux (xclip/xsel), Windows")

    def run_agent(self, prompt: str):
        """Run the agent with the given prompt."""
        try:
            from agent import new_main
            new_main(prompt=prompt)
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
            from agent import new_main
            new_main(prompt=None, start_from_base=None)  # This will trigger fix mode internally
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

    # --- HELPER METHODS ---
    def file_received_callback(self, file_path: str, success: bool):
        """Callback when a file transfer is complete."""
        if success:
            print(f"✓ File received successfully: {file_path}")

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
            action_logger = ActionLogger()
            version_control = VersionControl(action_logger, path_to_security_backup="__TEMP_SECURITY_BACKUP")
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

    def on_start(self):
        from coding.non_callable_tools.helpers import cleanup_old_logs
        cleanup_old_logs()
        self.patch_to_apply = None

    def run_server(self, host: str = "127.0.0.1", port: int = 5555):
        # start server
        self.server_instance = GameServer(host, port)

        # start server in a thread
        self.server_thread = threading.Thread(target=self.server_instance.start)
        self.server_thread.start()
        
    def connect_to_server(self, server_host: str = "127.0.0.1", server_port: int = 5555):
        # Connect to the server, creating client if needed or reconnecting if disconnected
        if not self.client:
            self.client = NetworkClient(server_host, server_port)

        # Only connect if not already connected
        self.client.disconnect()
        print(f"Attempting to connect to server at {server_host}:{server_port}...")
        if not self.client.connect(self.player_id):
            print("Failed to connect to server!")
            return False

        # Set up callbacks (do this every time in case they were reset)
        self.client.on_file_received = self.file_received_callback
        self.client.on_file_transfer_progress = self.file_transfer_progress_callback
        self.client.on_name_rejected = self.name_rejected_callback
        self.client.on_game_start = self.game_start_callback
        self.client.on_patch_received = self.patch_received_callback
        self.client.on_patch_sync_failed = self.patch_sync_failed_callback
        self.client.on_patch_merge_failed = self.patch_merge_failed_callback

        return True


    def create_room(self):
        # start server
        self.run_server(self.server_host, self.server_port)
        self.connect_to_server("localhost", self.server_port) # localhost is the server host and we are on the same machine

    
    def start_game(self):
        """Start the game."""
        print("🚀 Launching game client...")
        # File sync should have already happened, patches applied
        # Now exit the menu loop and start the game client
        self.running = False  # Exit the menu loop
        # Don't quit pygame here - run_client will handle it

        # Start the game client after menu cleanup
        run_client(network_client=self.client, player_id=self.player_id)

if __name__ == "__main__":
    # Test the menu system
    menu = BaseMenu()
    menu.run_menu_loop()
