from BASE_components.BASE_platform import BasePlatform
import pygame
import math

class Platform(BasePlatform):
    def __init__(self, x: float, y: float, width: float, height: float, color=(50, 200, 50)):
        # EXAMPLE: Change default color to a nice Green
        super().__init__(x, y, width, height, color)
        self.float_x = float(x)
        self.float_y = float(y)
        self.original_x = float(x)
        self.original_y = float(y)
        self.being_pulled = False

    def draw(self, screen: pygame.Surface):
        # EXAMPLE: Add a small border to the platform
        pygame.draw.rect(screen, (0, 100, 0), self.rect, 2)
        super().draw(screen)

    def move(self, dx: float, dy: float):
        self.float_x += dx
        self.float_y += dy
        self.rect.x = int(self.float_x)
        self.rect.y = int(self.float_y)

    def return_to_origin(self, delta_time, return_speed=100.0):
        dx = self.original_x - self.float_x
        dy = self.original_y - self.float_y
        dist = math.hypot(dx, dy)

        if dist > 0.5:
            # Calculate normalized direction
            dir_x = dx / dist
            dir_y = dy / dist
            
            # Calculate step distance
            move_dist = return_speed * delta_time
            
            # Don't overshoot
            if move_dist > dist:
                move_dist = dist
                
            self.move(dir_x * move_dist, dir_y * move_dist)
        else:
            self.float_x = self.original_x
            self.float_y = self.original_y
            self.rect.x = int(self.float_x)
            self.rect.y = int(self.float_y)