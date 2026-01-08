import pygame
import math
from BASE_files.BASE_network import NetworkObject

class BaseProjectile(NetworkObject):
    def __init__(self, x: float, y: float, direction: [float, float], speed: float, damage: float, owner_id: str, width: float = 10, height: float = 10):
        # Initialize network capabilities first
        super().__init__()
        # Network identity is automatically set by NetworkObject.__init__

        self.location = [x, y] # [x, y] in world coordinates (y-up)
        self.direction = direction # Normalized vector [x, y]
        self.speed = speed
        self.damage = damage
        self.owner_id = owner_id # To prevent hitting self
        self.width = width
        self.height = height
        self.active = True
        self.color = (255, 255, 0) # Yellow
        self.is_persistent = False # If True, Arena won't remove it on hit
        self.skip_collision_damage = False # If True, Arena won't deal damage in handle_collisions

        # Initialize graphics (can be called later for headless mode)
        self.init_graphics()

    def init_graphics(self):
        """
        Initialize graphics resources.
        Safe to call multiple times and works even if pygame is not initialized.
        """
        super().init_graphics()

        # Only initialize pygame-dependent graphics if pygame is available
        try:
            # Test if pygame is initialized by checking if we can create a surface
            pygame.display.get_surface()
            # If we get here, pygame is initialized, so we can load graphics
            # For projectiles, we don't have complex graphics to load currently
            pass
        except:
            # Pygame not initialized or no display - skip graphics initialization
            pass

    def update(self, delta_time: float):
        # Scale speed by delta_time (assuming speed is pixels per frame at 60fps)
        speed_multiplier = self.speed * (delta_time * 60)
        self.location[0] += self.direction[0] * speed_multiplier
        self.location[1] += self.direction[1] * speed_multiplier
        
        # Simple bounds check (optional, arena should handle removal)
        if self.location[1] < -100: # Below ground
            self.active = False

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(self.location[0], self.location[1], self.width, self.height)
    

    def draw(self, screen: pygame.Surface, arena_height: float):
        if not self.active or not self._graphics_initialized:
            return

        # Map y-up to pygame y-down
        py_y = arena_height - self.location[1] - self.height
        py_rect = pygame.Rect(self.location[0], py_y, self.width, self.height)
        pygame.draw.ellipse(screen, self.color, py_rect)
