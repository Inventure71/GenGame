import pygame
from BASE_components.BASE_network import NetworkObject

class BasePlatform(NetworkObject):
    def __init__(self, x: float, y: float, width: float, height: float, color=(100, 100, 100), health: float = 100.0):
        # Initialize network capabilities first
        super().__init__()
        self._set_network_identity("BASE_components.BASE_platform", "BasePlatform")

        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.health = health
        self.is_destroyed = False

        # Store width and height as attributes for serialization
        self.width = width
        self.height = height

        # Physics properties (moved from GAME_platform for compatibility)
        self.float_x = float(x)
        self.float_y = float(y)
        self.original_x = float(x)
        self.original_y = float(y)
        self.being_pulled = False

        # Initialize graphics (can be called later for headless mode)
        self.init_graphics()

    def init_graphics(self):
        """
        Initialize graphics resources.
        Safe to call multiple times and works even if pygame is not initialized.
        """
        super().init_graphics()

        # Reconstruct rect from stored position data if it's missing (after deserialization)
        if not hasattr(self, 'rect') or self.rect is None:
            self.rect = pygame.Rect(int(self.float_x), int(self.float_y), int(self.width), int(self.height))

        # Only initialize pygame-dependent graphics if pygame is available
        try:
            # Test if pygame is initialized by checking if we can create a surface
            pygame.display.get_surface()
            # If we get here, pygame is initialized - additional setup if needed
            pass
        except:
            # Pygame not initialized or no display - skip graphics initialization
            pass

    def move(self, dx: float, dy: float):
        """Move the platform by [dx, dy]."""
        self.float_x += dx
        self.float_y += dy
        self.rect.x = int(self.float_x)
        self.rect.y = int(self.float_y)

    def return_to_origin(self, delta_time: float, return_speed: float = 100.0):
        """Gradually move back to original position."""
        import math
        dx = self.original_x - self.float_x
        dy = self.original_y - self.float_y
        dist = math.hypot(dx, dy)

        if dist > 0.5:
            move_dist = min(dist, return_speed * delta_time)
            self.move((dx / dist) * move_dist, (dy / dist) * move_dist)
        else:
            self.float_x = self.original_x
            self.float_y = self.original_y
            self.rect.x = int(self.float_x)
            self.rect.y = int(self.float_y)

    def take_damage(self, amount: float):
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.is_destroyed = True

    def draw(self, screen: pygame.Surface, arena_height: float = None):
        if self.is_destroyed or not self._graphics_initialized:
            return
        pygame.draw.rect(screen, self.color, self.rect)

