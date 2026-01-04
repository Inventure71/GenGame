import pygame
import math

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
        if not self.active:
            return
        
        # Map y-up to pygame y-down
        py_y = arena_height - self.location[1] - self.height
        py_rect = pygame.Rect(self.location[0], py_y, self.width, self.height)
        pygame.draw.ellipse(screen, self.color, py_rect)

