from BASE_components.BASE_weapon import BaseWeapon
from GameFolder.projectiles.GAME_projectile import Projectile, StormCloud
import pygame
import time
import math

class Weapon(BaseWeapon):
    def __init__(self, name: str = "Basic Gun", damage: float = 10, cooldown: float = 0.5, projectile_speed: float = 20.0, location: [float, float] = None):
        super().__init__(name, damage, cooldown, projectile_speed, location)
        
        # EXAMPLE: Customize weapon appearance - make them bigger and more visible
        self.width = 40  # Bigger than base
        self.height = 25
        self.pickup_radius = 50  # Easier to pick up
        self.last_secondary_time = 0.0
        
        # Color coding by weapon type
        if "Pistol" in name:
            self.color = (150, 150, 255)  # Bright blue
        elif "Rifle" in name:
            self.color = (255, 100, 100)  # Bright red
        elif "Shotgun" in name:
            self.color = (100, 255, 100)  # Bright green
        elif "SMG" in name:
            self.color = (255, 255, 100)  # Yellow
        elif "Sniper" in name:
            self.color = (255, 100, 255)  # Magenta
        else:
            self.color = (200, 200, 200)  # Default gray

    def shoot(self, owner_x: float, owner_y: float, target_x: float, target_y: float, owner_id: str):
        if not self.can_shoot():
            return None

        self.last_shot_time = time.time()

        dx = target_x - owner_x
        dy = target_y - owner_y
        dist = math.hypot(dx, dy)

        if dist == 0:
            direction = [1, 0]
        else:
            direction = [dx / dist, dy / dist]

        # Create basic projectile
        projectile = Projectile(owner_x, owner_y, direction, self.projectile_speed, self.damage, owner_id)
        return projectile

    def secondary_fire(self, owner_x: float, owner_y: float, target_x: float, target_y: float, owner_id: str):
        if (time.time() - self.last_secondary_time) < self.cooldown:
            return None
        self.last_secondary_time = time.time()
        return None

    def special_fire(self, owner_x: float, owner_y: float, target_x: float, target_y: float, owner_id: str, is_holding: bool):
        return None

    def draw(self, screen: pygame.Surface, arena_height: float):
        """
        EXAMPLE: Custom weapon drawing with very visible styling.
        """
        if self.is_equipped:
            return
        
        # Convert y-up to pygame y-down
        py_y = arena_height - self.location[1] - self.height
        weapon_rect = pygame.Rect(self.location[0], py_y, self.width, self.height)
        
        # Draw glow/outline effect to make it super visible
        glow_rect = pygame.Rect(self.location[0] - 3, py_y - 3, self.width + 6, self.height + 6)
        pygame.draw.rect(screen, (255, 255, 255, 100), glow_rect, 3)
        
        # Draw weapon body with gradient effect
        pygame.draw.rect(screen, self.color, weapon_rect)
        
        # Add highlight
        lighter = tuple(min(255, c + 50) for c in self.color)
        highlight_rect = pygame.Rect(self.location[0], py_y, self.width, self.height // 3)
        pygame.draw.rect(screen, lighter, highlight_rect)
        
        # Thick white border
        pygame.draw.rect(screen, (255, 255, 255), weapon_rect, 3)
        
        # Draw weapon name with bigger, more visible text
        font = pygame.font.Font(None, 20)
        text = font.render(self.name, True, (255, 255, 255))
        text_rect = text.get_rect(center=(self.location[0] + self.width/2, py_y - 15))
        
        # Text background for readability
        bg_rect = text_rect.inflate(8, 4)
        pygame.draw.rect(screen, (0, 0, 0, 180), bg_rect)
        pygame.draw.rect(screen, (255, 255, 255), bg_rect, 1)
        
        # Text shadow
        shadow = font.render(self.name, True, (0, 0, 0))
        shadow_rect = text_rect.copy()
        shadow_rect.x += 1
        shadow_rect.y += 1
        screen.blit(shadow, shadow_rect)
        screen.blit(text, text_rect)

class StormBringer(Weapon):
    def __init__(self, location=None):
        super().__init__("Storm Bringer", damage=0.2, cooldown=3.0, projectile_speed=12.0, location=location)
        self.color = (30, 30, 120)  # Dark Blue

    def shoot(self, owner_x: float, owner_y: float, target_x: float, target_y: float, owner_id: str):
        if not self.can_shoot():
            return None

        self.last_shot_time = time.time()
        return [StormCloud(owner_x, owner_y, [target_x, target_y], owner_id)]