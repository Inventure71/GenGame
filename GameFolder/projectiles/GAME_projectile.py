from BASE_components.BASE_projectile import BaseProjectile
import pygame
import math
import random

class Projectile(BaseProjectile):
    def __init__(self, x: float, y: float, direction: [float, float], speed: float, damage: float, owner_id: str, width: float = 10, height: float = 10):
        super().__init__(x, y, direction, speed, damage, owner_id, width, height)
        # EXAMPLE: Change default color to blue
        self.color = (0, 100, 255) # Blue color

    def draw(self, screen: pygame.Surface, arena_height: float):
        if not self.active:
            return

        # Map y-up to pygame y-down
        py_y = arena_height - self.location[1] - self.height
        py_rect = pygame.Rect(self.location[0], py_y, self.width, self.height)
        # EXAMPLE: Add a small glow effect
        pygame.draw.ellipse(screen, (150, 200, 255), py_rect) # Light blue glow
        pygame.draw.ellipse(screen, self.color, py_rect)

class StormCloud(Projectile):
    def __init__(self, x, y, target_pos, owner_id):
        # Initialize with dummy direction, speed 5, damage 0.2
        super().__init__(x, y, [0, 0], 5, 0.2, owner_id, 80, 40)
        self.target_pos = target_pos
        self.is_raining = False
        self.rain_duration = 6.0
        self.rain_timer = 0.0
        self.persistent = True
        self.damage = 0.2
        self.width = 80
        self.height = 40

    def update(self, delta_time):
        if not self.is_raining:
            dx = self.target_pos[0] - self.location[0]
            dy = self.target_pos[1] - self.location[1]
            dist = math.hypot(dx, dy)
            move_dist = self.speed * (delta_time * 60)
            if dist <= move_dist:
                self.location[0] = self.target_pos[0]
                self.location[1] = self.target_pos[1]
                self.is_raining = True
            else:
                self.location[0] += (dx / dist) * move_dist
                self.location[1] += (dy / dist) * move_dist
        
        if self.is_raining:
            self.rain_timer += delta_time
            if self.rain_timer >= self.rain_duration:
                self.active = False

    def draw(self, screen, arena_height):
        if not self.active:
            return

        py_y = arena_height - self.location[1] - self.height
        py_rect = pygame.Rect(self.location[0], py_y, self.width, self.height)
        
        pygame.draw.ellipse(screen, (100, 100, 100), py_rect)
        
        if self.is_raining:
            for _ in range(10):
                rx = random.randint(int(self.location[0]), int(self.location[0] + self.width))
                ry_start = arena_height - self.location[1]
                ry_end = arena_height
                pygame.draw.line(screen, (0, 0, 255), (rx, ry_start), (rx, ry_end), 1)
            
            if random.random() < 0.05:
                pygame.draw.ellipse(screen, (255, 255, 255), py_rect)
                lx = self.location[0] + self.width // 2
                ly = arena_height - self.location[1]
                points = [(lx, ly)]
                curr_y = ly
                curr_x = lx
                while curr_y < arena_height:
                    curr_y += 20
                    curr_x += random.randint(-15, 15)
                    points.append((curr_x, min(curr_y, arena_height)))
                if len(points) > 1:
                    pygame.draw.lines(screen, (255, 255, 255), False, points, 2)