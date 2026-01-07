import pygame
import math
from BASE_components.network_protocol import ProjectileState

class BaseProjectile:
    def __init__(self, x: float, y: float, direction: [float, float], speed: float, damage: float, owner_id: str, width: float = 10, height: float = 10):
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
        self.network_id = None # Unique ID for network sync
        self.meta = 0 # Generic byte for extra state (e.g. type variant, target index)

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
    
    def get_network_state(self, type_id: int, owner_numeric_id: int) -> ProjectileState:
        """Create a state packet for this projectile."""
        return ProjectileState(
            proj_id=self.network_id if self.network_id is not None else 0,
            proj_type=type_id,
            x=self.location[0],
            y=self.location[1],
            dir_x=self.direction[0],
            dir_y=self.direction[1],
            owner_id=owner_numeric_id,
            meta=self.meta
        )

    def apply_network_state(self, state: ProjectileState):
        """Apply state packet to this projectile."""
        self.location[0] = state.x
        self.location[1] = state.y
        self.direction = [state.dir_x, state.dir_y]
        self.meta = state.meta
        self.active = True

    def draw(self, screen: pygame.Surface, arena_height: float):
        if not self.active:
            return
        
        # Map y-up to pygame y-down
        py_y = arena_height - self.location[1] - self.height
        py_rect = pygame.Rect(self.location[0], py_y, self.width, self.height)
        pygame.draw.ellipse(screen, self.color, py_rect)
