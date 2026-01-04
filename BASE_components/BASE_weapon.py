from BASE_components.BASE_projectile import BaseProjectile
import pygame
import time
import math

class BaseWeapon:
    def __init__(self, name: str, damage: float, cooldown: float, projectile_speed: float, location: [float, float] = None):
        self.name = name
        self.damage = damage
        self.cooldown = cooldown # Seconds between shots
        self.projectile_speed = projectile_speed
        self.last_shot_time = 0.0
        
        # Pickup properties
        self.location = location if location else [0, 0]  # World coordinates [x, y]
        self.is_equipped = False  # True when held by a character, False when on ground
        self.width = 30  # Visual size when on ground
        self.height = 20
        self.pickup_radius = 40  # Collision radius for pickup
        self.color = (100, 100, 200)  # Default blue color

    def can_shoot(self) -> bool:
        return (time.time() - self.last_shot_time) >= self.cooldown

    def shoot(self, owner_x: float, owner_y: float, target_x: float, target_y: float, owner_id: str) -> BaseProjectile:
        if not self.can_shoot():
            return None

        self.last_shot_time = time.time()

        # Calculate direction vector
        dx = target_x - owner_x
        dy = target_y - owner_y
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance == 0:
            direction = [1, 0] # Default to right if target is on self
        else:
            direction = [dx / distance, dy / distance]

        return BaseProjectile(
            x=owner_x,
            y=owner_y,
            direction=direction,
            speed=self.projectile_speed,
            damage=self.damage,
            owner_id=owner_id
        )

    def drop(self, location: [float, float]):
        """
        Drop the weapon at the specified location.
        """
        self.location = location.copy()
        self.is_equipped = False

    def pickup(self):
        """
        Mark the weapon as equipped (picked up).
        """
        self.is_equipped = True

    def get_pickup_rect(self, arena_height: float) -> pygame.Rect:
        """
        Get the collision rect for pickup detection.
        Returns rect in pygame screen coordinates.
        """
        py_y = arena_height - self.location[1] - self.height
        return pygame.Rect(
            self.location[0] - self.pickup_radius / 2,
            py_y - self.pickup_radius / 2,
            self.pickup_radius,
            self.pickup_radius
        )

    def draw(self, screen: pygame.Surface, arena_height: float):
        """
        Draw the weapon on the ground (only when not equipped).
        """
        if self.is_equipped:
            return
        
        # Convert y-up to pygame y-down
        py_y = arena_height - self.location[1] - self.height
        weapon_rect = pygame.Rect(self.location[0], py_y, self.width, self.height)
        
        # Draw weapon body
        pygame.draw.rect(screen, self.color, weapon_rect)
        pygame.draw.rect(screen, (255, 255, 255), weapon_rect, 2)  # White border
        
        # Draw weapon name (small text)
        font = pygame.font.Font(None, 16)
        text = font.render(self.name[:8], True, (255, 255, 255))
        text_rect = text.get_rect(center=(self.location[0] + self.width/2, py_y - 10))
        screen.blit(text, text_rect)

