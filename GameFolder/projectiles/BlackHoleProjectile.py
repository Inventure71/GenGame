import pygame
import math
import random
from GameFolder.projectiles.GAME_projectile import Projectile

class BlackHoleProjectile(Projectile):
    def __init__(self, x, y, target_x, target_y, owner_id):
        super().__init__(x, y, [0, 0], speed=400.0, damage=0.5, owner_id=owner_id, width=60, height=60)
        self.pull_radius = 250
        self.pull_strength = 5.0
        self.duration = 5.0
        self.timer = 0.0
        self.target_pos = (target_x, target_y)
        self.is_stationary = False
        self.is_persistent = True

    def update(self, delta_time):
        if not self.active:
            return

        if not self.is_stationary:
            dx = self.target_pos[0] - self.location[0]
            dy = self.target_pos[1] - self.location[1]
            dist = math.hypot(dx, dy)
            if dist < 10:
                self.is_stationary = True
                self.location[0], self.location[1] = self.target_pos
            else:
                move_dist = self.speed * delta_time
                if move_dist > dist:
                    move_dist = dist
                self.location[0] += (dx / dist) * move_dist
                self.location[1] += (dy / dist) * move_dist
        else:
            self.timer += delta_time
            if self.timer >= self.duration:
                self.active = False

    def draw(self, screen, arena_height):
        if not self.active:
            return

        center_x = self.location[0]
        center_y = arena_height - self.location[1]
        pulse = math.sin(self.timer * 12) * 4
        base_radius = (self.width / 2) + pulse

        pygame.draw.circle(screen, (106, 13, 173), (int(center_x), int(center_y)), int(base_radius + 10))
        pygame.draw.circle(screen, (255, 0, 255), (int(center_x), int(center_y)), int(base_radius))
        pygame.draw.circle(screen, (0, 0, 0), (int(center_x), int(center_y)), int(base_radius - 5))

        for i in range(6):
            angle = self.timer * 15 + (i * math.pi / 3)
            dist = base_radius * 0.8
            sx = center_x + math.cos(angle) * dist
            sy = center_y + math.sin(angle) * dist
            color = (147, 112, 219) if i % 2 == 0 else (75, 0, 130)
            pygame.draw.circle(screen, color, (int(sx), int(sy)), 6)