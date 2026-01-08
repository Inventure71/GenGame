from BASE_components.BASE_projectile import BaseProjectile
from BASE_files.BASE_network import NetworkObject
import pygame
import time
import math

class BaseWeapon(NetworkObject):
    def __init__(self, name: str, damage: float, cooldown: float, projectile_speed: float, max_ammo: int = 30, ammo_per_shot: int = 1, location: [float, float] = None):
        # Initialize network capabilities first
        super().__init__()
        # Network identity is automatically set by NetworkObject.__init__

        self.name = name
        self.damage = damage
        self.cooldown = cooldown # Seconds between shots
        self.projectile_speed = projectile_speed
        self.last_shot_time = 0.0
        
        # Ammo system
        self.max_ammo = max_ammo  # Maximum ammo capacity
        self.ammo = max_ammo  # Current ammo (starts full)
        self.ammo_per_shot = ammo_per_shot  # Ammo consumed per shot
        
        # Pickup properties
        self.location = location if location else [0, 0]  # World coordinates [x, y]
        self.is_equipped = False  # True when held by a character, False when on ground
        self.width = 30  # Visual size when on ground
        self.height = 20
        self.pickup_radius = 40  # Collision radius for pickup
        self.color = (100, 100, 200)  # Default blue color

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
            # For weapons, we might load fonts here if needed
            pass
        except:
            # Pygame not initialized or no display - skip graphics initialization
            pass

    def can_shoot(self) -> bool:
        """Check if weapon can shoot (cooldown elapsed AND has ammo)."""
        return (time.time() - self.last_shot_time) >= self.cooldown and self.ammo >= self.ammo_per_shot

    def shoot(self, owner_x: float, owner_y: float, target_x: float, target_y: float, owner_id: str) -> BaseProjectile:
        if not self.can_shoot():
            return None

        # Consume ammo
        self.ammo -= self.ammo_per_shot
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

    def add_ammo(self, amount: int):
        """
        Add ammo to the weapon (used by ammo pickups).
        Cannot exceed max_ammo.
        """
        self.ammo = min(self.max_ammo, self.ammo + amount)
        
    def reload(self):
        """
        Reload weapon to full ammo capacity.
        """
        self.ammo = self.max_ammo

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
        if self.is_equipped or not self._graphics_initialized:
            return

        # Convert y-up to pygame y-down
        py_y = arena_height - self.location[1] - self.height
        weapon_rect = pygame.Rect(self.location[0], py_y, self.width, self.height)

        # Draw weapon body
        pygame.draw.rect(screen, self.color, weapon_rect)
        pygame.draw.rect(screen, (255, 255, 255), weapon_rect, 2)  # White border

        # Draw weapon name and ammo (small text)
        font = pygame.font.Font(None, 16)
        display_text = f"{self.name[:8]} ({self.ammo}/{self.max_ammo})"
        text = font.render(display_text, True, (255, 255, 255))
        text_rect = text.get_rect(center=(self.location[0] + self.width/2, py_y - 10))
        screen.blit(text, text_rect)

