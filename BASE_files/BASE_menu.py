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
        width, height = 1200, 700  # Match server arena dimensions
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

        # Game menu
        self.on_start()
        
        print("Creating window...")
        self.screen = pygame.display.set_mode((1200, 700))

        print(f"Video Driver: {pygame.display.get_driver()}")

        pygame.display.set_caption("GenGame - Multiplayer Menu")
        print("Window created successfully.")
        self.clock = pygame.time.Clock()
        self.running = True

        # Menu state
        self.current_menu = "main"  # main, create_room, join_room, library, room
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

        self.client = None
        self.server_thread = None
        self.server_instance = None  # Store server instance for shutdown
        self.server_host = "127.0.0.1"
        self.server_port = 5555
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
        field_x = (1200 - field_width) // 2  # Center horizontally
        field_y = 20

        player_id_rect = self.draw_text_field(self.player_id, field_x, field_y, field_width, field_height,
                                             self.player_id_focused, "Enter Player ID")

        # Handle clicking on the text field
        if self.check_button_click(player_id_rect):
            self.player_id_focused = True
        elif self.mouse_clicked and not player_id_rect.collidepoint(self.mouse_pos):
            self.player_id_focused = False

        # Title
        self.draw_text("GEN GAME", 600, 120, self.menu_font, center=True)

        # Subtitle
        self.draw_text("Multiplayer Gaming Platform", 600, 180, self.small_font, center=True)

        # Buttons
        center_x = 600
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

        # Settings Button
        settings_rect = self.draw_button("Settings", center_x - self.button_width//2, button_y + button_spacing * 3,
                                        self.button_width, self.button_height,
                                        self.check_button_hover(center_x - self.button_width//2, button_y + button_spacing * 3, self.button_width, self.button_height))
        if self.check_button_click(settings_rect):
            self.on_settings_click()

        # Quit Button
        quit_rect = self.draw_button("Quit", center_x - self.button_width//2, button_y + button_spacing * 4,
                                    self.button_width, self.button_height,
                                    self.check_button_hover(center_x - self.button_width//2, button_y + button_spacing * 4, self.button_width, self.button_height))
        if self.check_button_click(quit_rect):
            self.on_quit_click()

        # Show error message if any (for a few seconds)
        if self.error_message and pygame.time.get_ticks() - self.error_message_time < 5000:  # 5 seconds
            self.draw_text(self.error_message, 600, 550, self.small_font, color=(255, 100, 100), center=True)
        elif self.error_message:
            # Clear old error message
            self.error_message = None

    def render_room_menu(self):
        """Render the room menu."""
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

        # Title
        self.draw_text("Game Room", 600, 80, self.menu_font, center=True)

        # Room status
        status_text = f"Status: {'Connected' if self.client and self.client.connected else 'Connecting...'}"
        self.draw_text(status_text, 600, 150, self.small_font, center=True)

        # Buttons
        center_x = 600
        button_y = 250
        button_spacing = 80

        # Start Game Button (only show if connected)
        if self.client and self.client.connected:
            start_rect = self.draw_button("Start Game", center_x - self.button_width//2, button_y,
                                         self.button_width, self.button_height,
                                         self.check_button_hover(center_x - self.button_width//2, button_y, self.button_width, self.button_height))
            if self.check_button_click(start_rect):
                self.on_start_game_click()
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
            self.draw_text(self.error_message, 600, 550, self.small_font, color=(255, 100, 100), center=True)
        elif self.error_message:
            # Clear old error message
            self.error_message = None

    def render_library_menu(self):
        """Render the game library menu."""
        self.screen.fill(self.menu_background_color)

        # Title
        self.draw_text("Game Library", 600, 80, self.menu_font, center=True)

        # Placeholder content
        self.draw_text("Available Games:", 200, 150, self.button_font)
        self.draw_text("(Game library functionality - PLACEHOLDER)", 200, 200, self.small_font)

        # Back Button
        back_rect = self.draw_button("Back", 450, 500, 300, 60,
                                    self.check_button_hover(450, 500, 300, 60))
        if self.check_button_click(back_rect):
            self.on_library_back_click()

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
                        print(f"Mouse clicked at {self.mouse_pos}")
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
        """Handle keyboard input for text fields."""
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
        print("Library clicked - PLACEHOLDER")
        self.show_menu("library")

    def on_settings_click(self):
        """Handle settings button click."""
        print("Settings clicked - PLACEHOLDER")
        # TODO: Show settings menu

    def on_quit_click(self):
        """Handle quit button click."""
        print("Quit clicked")
        self.running = False

    def on_start_game_click(self):
        """Handle start game button click."""
        print("Start Game clicked - requesting game start")
        if self.client and self.client.connected:
            self.client.request_start_game()
        else:
            print("Not connected to server!")

    def on_leave_room_click(self):
        """Handle leave room button click."""
        print("Leave Room clicked - PLACEHOLDER")
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

    # --- HELPER METHODS ---
    def file_received_callback(self, file_path: str, success: bool):
        """Callback when a file transfer is complete."""
        if success:
            print(f"✓ File received successfully: {file_path}")

            new_path = os.path.join(os.path.dirname(__file__), "GameFolder", file_path.split("/")[-1])
            shutil.move(file_path, new_path)

            self.patch_to_apply = new_path
            
            #if new_path.endswith('.json'):
            #    self.load_patch_from_file(new_path)
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
        print(f"DEBUG: Current working directory: {os.getcwd()}")
        print(f"DEBUG: Script location: {os.path.abspath(__file__)}")
        print(f"DEBUG: Project root would be: {os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}")

        # CRITICAL FIX: Ensure we're applying patches from the project root directory
        # VersionControl.apply_all_changes applies patches relative to current working directory
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        original_cwd = os.getcwd()

        # Change to project root to ensure patches are applied correctly
        if os.getcwd() != project_root:
            print(f"DEBUG: Changing working directory from {os.getcwd()} to {project_root}")
            os.chdir(project_root)

        try:
            # Import version control system to apply the patch
            action_logger = ActionLogger()
            version_control = VersionControl(action_logger, path_to_security_backup="__TEMP_SECURITY_BACKUP")
            print(f"DEBUG: About to call apply_all_changes with patch_path: {patch_path}")
            print(f"DEBUG: Working directory is now: {os.getcwd()}")
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
                self.client.send_patch_applied(success=True)
                #self.client.send_patch_applied(success=False, error_message=errors)
        except Exception as e:
            print(f"Error applying patch: {e}")
            self.client.send_patch_applied(success=True)
            #self.client.send_patch_applied(success=False, error_message=str(e))
        finally:
            # Always restore original working directory
            if os.getcwd() != original_cwd:
                print(f"DEBUG: Restoring working directory to {original_cwd}")
                os.chdir(original_cwd)

    def patch_sync_failed_callback(self, reason: str, failed_clients: list, details: list):
        """Callback when patch synchronization fails on one or more clients."""
        print(f"❌ Game start aborted: {reason}")
        error_msg = f"Game cannot start - Patch failed on: {', '.join(failed_clients)}"
        self.show_error_message(error_msg)

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

        return True

    def sync_patch_file(self, patch_name: str):
        # sync the patch file from the server
        self.client.request_file(patch_name)

    def create_room(self):
        # start server
        self.run_server(self.server_host, self.server_port)
        self.connect_to_server("localhost", self.server_port) # localhost is the server host and we are on the same machine

    def create_new_patch(self):
        """Create a new patch - PLACEHOLDER."""
        print("Create new patch - PLACEHOLDER")
        # TODO: Implement patch creation UI
    
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
