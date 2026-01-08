import os

# Set video driver BEFORE importing pygame
os.environ['SDL_VIDEODRIVER'] = 'cocoa'

import shutil
import threading
import pygame

from BASE_files.network_client import NetworkClient
from server import GameServer

# Features:
# - Main menu
# -- Create/Join room
# - Library
# -- View/Download/Install/Update games
# - Room
# -- You are in a room and you sync asking the server for the game files
# -- You can vote to start the game

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
        self.in_room = False
        self.room_code = ""
        self.available_games = []

        self.client = None
        self.server_thread = None
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

    def show_menu(self, menu_name: str):
        """Switch to a different menu."""
        self.current_menu = menu_name

    def check_button_click(self, button_rect: pygame.Rect) -> bool:
        """Check if a button was clicked."""
        return self.mouse_clicked and button_rect.collidepoint(self.mouse_pos)

    def render_main_menu(self):
        """Render the main menu."""
        self.screen.fill(self.menu_background_color)

        # Title
        self.draw_text("GEN GAME", 600, 80, self.menu_font, center=True)

        # Subtitle
        self.draw_text("Multiplayer Gaming Platform", 600, 140, self.small_font, center=True)

        # Buttons
        center_x = 600
        button_y = 200
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

    def render_room_menu(self):
        """Render the room menu."""
        self.screen.fill(self.menu_background_color)

        # Title
        self.draw_text("Game Room", 600, 80, self.menu_font, center=True)

        # Room status
        status_text = f"Status: {'Connected' if self.client and self.client.connected else 'Not Connected'}"
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
        if self.frame_count % 60 == 0:
            print(f"Rendering frame {self.frame_count}... (Menu: {self.current_menu})")
            
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

            self.render()

        print("Menu loop finished.")
        pygame.quit()

    # Placeholder methods for menu actions
    def on_create_room_click(self):
        """Handle create room button click."""
        print("Create Room clicked - PLACEHOLDER")
        self.create_room()
        self.show_menu("room")

    def on_join_room_click(self):
        """Handle join room button click."""
        print("Join Room clicked - PLACEHOLDER")
        # TODO: Show join room dialog
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
        print("Start Game clicked - PLACEHOLDER")
        # TODO: Start the actual game

    def on_leave_room_click(self):
        """Handle leave room button click."""
        print("Leave Room clicked - PLACEHOLDER")
        self.show_menu("main")

    def on_back_to_menu_click(self):
        """Handle back to menu button click."""
        print("Back to Menu clicked")
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
            
            #if new_path.endswith('.json'):
            #    self.load_patch_from_file(new_path)
        else:
            print(f"✗ Failed to receive file: {file_path}")
    
    def file_transfer_progress_callback(self,file_path: str, progress: float, direction: str):
        """Callback for file transfer progress updates."""
        print(f"File transfer progress: {direction} {file_path}: {progress*100:.1f}%")

    def on_start(self):
        from coding.non_callable_tools.helpers import cleanup_old_logs
        cleanup_old_logs()

    def run_server(self, host: str = "127.0.0.1", port: int = 5555):
        # start server
        server = GameServer(host, port)
        
        # start server in a thread
        self.server_thread = threading.Thread(target=server.start)
        self.server_thread.start()
        
    def connect_to_server(self, server_host: str = "127.0.0.1", server_port: int = 5555):
        # menu with a text area for the server address and a button to connect to the server
        if not self.client:
            self.client = NetworkClient(server_host, server_port)
            if not self.client.connect(self.player_id):
                print("Failed to connect to server!")
                return

        # Set up callbacks
        self.client.on_file_received = self.file_received_callback
        self.client.on_file_transfer_progress = self.file_transfer_progress_callback

    def sync_patch_file(self, patch_name: str):
        # sync the patch file from the server
        self.client.request_file(patch_name)

    def create_room(self):
        # start server
        self.run_server(self.server_host, self.server_port)
        self.connect_to_server("localhost", self.server_port) # localhost is the server host and we are on the same machine

    def join_room(self, server_host: str = "127.0.0.1", server_port: int = 5555):
        # join the room
        self.connect_to_server(server_host, server_port)

    def create_new_patch(self):
        """Create a new patch - PLACEHOLDER."""
        print("Create new patch - PLACEHOLDER")
        # TODO: Implement patch creation UI


if __name__ == "__main__":
    # Test the menu system
    menu = BaseMenu()
    menu.run_menu_loop()
