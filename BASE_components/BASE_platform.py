import pygame

class BasePlatform:
    def __init__(self, x: float, y: float, width: float, height: float, color=(100, 100, 100), health: float = 100.0):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.health = health
        self.is_destroyed = False
        
        # Physics properties (moved from GAME_platform for compatibility)
        self.float_x = float(x)
        self.float_y = float(y)
        self.original_x = float(x)
        self.original_y = float(y)
        self.being_pulled = False
    
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

    def draw(self, screen: pygame.Surface):
        if self.is_destroyed:
            return
        pygame.draw.rect(screen, self.color, self.rect)

