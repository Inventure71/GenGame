from GameFolder.weapons.GAME_weapon import Weapon
from GameFolder.projectiles.OrbitalProjectiles import TargetingLaser
import time
import math
import pygame

class OrbitalCannon(Weapon):
    def __init__(self, location=None):
        super().__init__(name="Orbital Cannon", damage=10, cooldown=2.0, projectile_speed=25.0, max_ammo=8, ammo_per_shot=1, location=location)
        self.color = (50, 50, 50)  # Dark Gray

    def shoot(self, owner_x, owner_y, target_x, target_y, owner_id):
        if not self.can_shoot():
            return []

        # Consume ammo
        self.ammo -= self.ammo_per_shot
        self.last_shot_time = time.time()

        dx = target_x - owner_x
        dy = target_y - owner_y
        dist = math.hypot(dx, dy)

        if dist == 0:
            direction = [1, 0]
        else:
            direction = [dx / dist, dy / dist]

        return [TargetingLaser(owner_x, owner_y, direction, owner_id, dist)]

    def draw(self, screen, arena_height):
        """
        Override draw to ensure dark gray body with a red highlight as specified.
        """
        if self.is_equipped:
            return
        
        # Convert y-up to pygame y-down
        py_y = arena_height - self.location[1] - self.height
        weapon_rect = pygame.Rect(self.location[0], py_y, self.width, self.height)
        
        # Glow/outline
        glow_rect = pygame.Rect(self.location[0] - 3, py_y - 3, self.width + 6, self.height + 6)
        pygame.draw.rect(screen, (255, 255, 255, 100), glow_rect, 3)
        
        # Dark gray body
        pygame.draw.rect(screen, self.color, weapon_rect)
        
        # Red highlight
        highlight_color = (200, 50, 50)
        highlight_rect = pygame.Rect(self.location[0], py_y, self.width, self.height // 3)
        pygame.draw.rect(screen, highlight_color, highlight_rect)
        
        # Border
        pygame.draw.rect(screen, (255, 255, 255), weapon_rect, 3)
        
        # Weapon name label
        font = pygame.font.Font(None, 20)
        text = font.render(self.name, True, (255, 255, 255))
        text_rect = text.get_rect(center=(self.location[0] + self.width/2, py_y - 15))
        
        bg_rect = text_rect.inflate(8, 4)
        pygame.draw.rect(screen, (0, 0, 0, 180), bg_rect)
        pygame.draw.rect(screen, (255, 255, 255), bg_rect, 1)
        
        screen.blit(text, text_rect)