import pygame
from BASE_files.BASE_network import NetworkObject


class BaseAmmoPickup(NetworkObject):
    """
    Represents an ammo pickup that can be collected by players.
    Adds ammo to their current weapon.
    """
    
    def __init__(self, location: [float, float], ammo_amount: int = 10):
        # Initialize network capabilities first
        super().__init__()
        self._set_network_identity("BASE_components.BASE_ammo", "BaseAmmoPickup")
        
        self.location = location if location else [0, 0]  # World coordinates [x, y]
        self.ammo_amount = ammo_amount  # Amount of ammo to give
        self.is_active = True  # False when picked up
        
        # Visual properties
        self.width = 20
        self.height = 15
        self.pickup_radius = 35  # Collision radius for pickup
        self.color = (255, 200, 0)  # Gold/yellow color
        
        # Initialize graphics (can be called later for headless mode)
        self.init_graphics()
    
    def init_graphics(self):
        """
        Initialize graphics resources.
        Safe to call multiple times and works even if pygame is not initialized.
        Thread-safe for testing scenarios.
        """
        super().init_graphics()

        # Skip pygame operations if we're in a thread other than the main thread
        # or if pygame operations might cause issues (like during testing)
        try:
            import threading
            if threading.current_thread() != threading.main_thread():
                # We're in a background thread, skip pygame operations
                return

            # Only initialize pygame-dependent graphics if pygame is available
            # and we're in the main thread
            pygame.display.get_surface()
            # If we get here, pygame is initialized
            pass
        except:
            # Pygame not initialized or no display - skip graphics initialization
            pass
    
    def pickup(self):
        """
        Mark the ammo pickup as collected.
        """
        self.is_active = False
    
    def get_pickup_rect(self, arena_height: float) -> pygame.Rect:
        """
        Get the collision rect for pickup detection.
        Returns rect in pygame screen coordinates.
        """
        py_y = arena_height - self.location[1] - self.height
        return pygame.Rect(
            self.location[0] - self.pickup_radius / 2,
            py_y - self.pickup_radius / 2,
            self.pickup_radius,
            self.pickup_radius
        )
    
    def draw(self, screen: pygame.Surface, arena_height: float):
        """
        Draw the ammo pickup on the ground.
        """
        if not self.is_active or not self._graphics_initialized:
            return
        
        # Convert y-up to pygame y-down
        py_y = arena_height - self.location[1] - self.height
        ammo_rect = pygame.Rect(self.location[0], py_y, self.width, self.height)
        
        # Draw glowing outline effect
        glow_rect = pygame.Rect(self.location[0] - 2, py_y - 2, self.width + 4, self.height + 4)
        pygame.draw.rect(screen, (255, 255, 100), glow_rect, 2)
        
        # Draw ammo box body
        pygame.draw.rect(screen, self.color, ammo_rect)
        
        # Draw border
        pygame.draw.rect(screen, (200, 150, 0), ammo_rect, 2)
        
        # Draw "A" for ammo
        font = pygame.font.Font(None, 16)
        text = font.render("A", True, (0, 0, 0))
        text_rect = text.get_rect(center=(self.location[0] + self.width/2, py_y + self.height/2))
        screen.blit(text, text_rect)
        
        # Draw ammo amount below
        font_small = pygame.font.Font(None, 12)
        amount_text = font_small.render(f"+{self.ammo_amount}", True, (255, 255, 255))
        amount_rect = amount_text.get_rect(center=(self.location[0] + self.width/2, py_y - 8))
        
        # Text background for readability
        bg_rect = amount_rect.inflate(4, 2)
        pygame.draw.rect(screen, (0, 0, 0, 180), bg_rect)
        screen.blit(amount_text, amount_rect)

