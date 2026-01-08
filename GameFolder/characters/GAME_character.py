from BASE_components.BASE_character import BaseCharacter
import pygame
import time

class Character(BaseCharacter):
    """
    GAME implementation of Character.
    Inherits improved movement and flight from BaseCharacter.
    """
    def __init__(self, name: str, description: str, image: str, location: [float, float], width: float = 50, height: float = 50):
        super().__init__(name, description, image, location, width, height)
        self.speed = 6.0
        self.color = (255, 255, 0) # Yellow

        # Shield system
        self.shield = 50.0  # Current shield amount
        self.max_shield = 50.0  # Maximum shield capacity
        self.shield_regen_rate = 1.0  # Shield points per second
        self.last_damage_time = 0  # Track when we last took damage

    def __setstate__(self, state):
        """Override to ensure shield properties are properly initialized from network data"""
        super().__setstate__(state)

        # Ensure shield properties exist (for backward compatibility)
        if not hasattr(self, 'shield'):
            self.shield = 50.0
        if not hasattr(self, 'max_shield'):
            self.max_shield = 50.0
        if not hasattr(self, 'shield_regen_rate'):
            self.shield_regen_rate = 1.0
        if not hasattr(self, 'last_damage_time'):
            self.last_damage_time = 0

    def take_damage(self, amount: float):
        """Override to implement shield system - shields take damage first"""
        if not self.is_alive or amount <= 0:
            return

        self.last_damage_time = time.time()

        # Shields take damage first
        if self.shield > 0:
            shield_damage = min(self.shield, amount)
            self.shield -= shield_damage
            amount -= shield_damage

        # Remaining damage goes to health
        if amount > 0:
            super().take_damage(amount)

    def update(self, delta_time: float, platforms: list = None, arena_height: float = 600):
        """Override to add shield regeneration"""
        # Call parent update first
        super().update(delta_time, platforms, arena_height)

        # Shield regeneration (only if alive and not recently damaged)
        current_time = time.time()
        if self.is_alive and current_time - self.last_damage_time > 1.0:  # 1 second delay after damage
            if self.shield < self.max_shield:
                self.shield = min(self.max_shield, self.shield + self.shield_regen_rate * delta_time)

    def draw(self, screen: pygame.Surface, arena_height: float):
        if not self.is_alive:
            return

        # Map y-up to pygame y-down
        py_y = arena_height - self.location[1] - (self.height * self.scale_ratio)
        py_rect = pygame.Rect(self.location[0], py_y, self.width * self.scale_ratio, self.height * self.scale_ratio)

        # Visual feedback for flight
        draw_color = self.color
        if self.is_currently_flying:
            # Blue tint for flying
            draw_color = (min(255, self.color[0] + 50), min(255, self.color[1] + 50), 255)
        
        pygame.draw.rect(screen, draw_color, py_rect)

        # UI bars
        bar_width = self.width * self.scale_ratio

        # Shield bar (top, cyan)
        if self.shield > 0:
            shield_ratio = self.shield / self.max_shield
            pygame.draw.rect(screen, (50, 50, 50), (self.location[0], py_y - 18, bar_width, 4))  # Background
            pygame.draw.rect(screen, (0, 255, 255), (self.location[0], py_y - 18, bar_width * shield_ratio, 4))  # Shield

        # Health bar (middle, green/red)
        health_ratio = self.health / self.max_health
        pygame.draw.rect(screen, (255, 0, 0), (self.location[0], py_y - 12, bar_width, 5))  # Background
        pygame.draw.rect(screen, (0, 255, 0), (self.location[0], py_y - 12, bar_width * health_ratio, 5))  # Health

        # Flight bar (bottom, blue/gray)
        flight_ratio = self.flight_time_remaining / self.max_flight_time
        bar_color = (0, 191, 255) if not self.needs_recharge else (100, 100, 100)
        pygame.draw.rect(screen, (40, 40, 40), (self.location[0], py_y - 6, bar_width, 3))  # Background
        pygame.draw.rect(screen, bar_color, (self.location[0], py_y - 6, bar_width * flight_ratio, 3))  # Flight

    def apply_gravity(self, arena_height: float = 600, platforms: list = None):
        """
        Override to remove floor boundary - allow falling out of arena.
        """
        if not self.is_alive:
            return

        # Don't apply gravity if actively flying
        if self.is_currently_flying:
            return

        # Update position based on vertical velocity
        self.location[1] += self.vertical_velocity
        # Apply gravity to velocity
        self.vertical_velocity -= self.gravity * self.gravity_multiplier

        # NO FLOOR BOUNDARY - players can fall out!
        # Only check platforms for landing
        self.on_ground = False

        # Check platforms
        if platforms and not self.is_dropping and self.vertical_velocity <= 0:
            char_rect = self.get_rect()
            # Feet position in screen coordinates
            py_feet_y = arena_height - self.location[1]

            for plat in platforms:
                # Check if character is falling towards platform
                # Character feet should be at or slightly below platform top
                feet_at_platform_level = abs(py_feet_y - plat.rect.top) < 20  # Balanced tolerance

                # Horizontal overlap check
                char_left = self.location[0]
                char_right = self.location[0] + char_rect.width
                horizontal_overlap = char_right > plat.rect.left and char_left < plat.rect.right

                if feet_at_platform_level and horizontal_overlap:
                    # Land on platform
                    self.location[1] = arena_height - plat.rect.top
                    self.vertical_velocity = 0
                    self.on_ground = True
                    self.hover_time = 0
                    break

    def move(self, direction: [float, float], platforms: list = None):
        """
        Override to remove floor boundary in flight logic and add platform collision.
        """
        if not self.can_move or not self.is_alive:
            return

        # Apply status effects like inverted physics
        actual_dir = [direction[0], direction[1]]
        if self.physics_inverted:
            actual_dir[0] *= -1
            actual_dir[1] *= -1

        # Update movement flags
        self.is_moving_up = (actual_dir[1] > 0)

        # Dropping logic: can only drop through platforms when actively pressing down
        self.is_dropping = (actual_dir[1] < -0.5)

        # Handle horizontal movement with platform collision
        if actual_dir[0] != 0 and platforms:
            new_x = self.location[0] + actual_dir[0] * self.speed * self.speed_multiplier

            # Create character rect in pygame coordinates for collision detection
            # Assume arena height of 700 (matches setup_battle_arena)
            arena_height = 700
            char_width = self.width * self.scale_ratio
            char_height = self.height * self.scale_ratio
            py_char_y = arena_height - self.location[1] - char_height  # Convert to pygame y-down

            # Test rectangle at new position
            test_rect = pygame.Rect(new_x, py_char_y, char_width, char_height)

            # Check horizontal collision with platforms
            collision = False
            for plat in platforms:
                if test_rect.colliderect(plat.rect):
                    collision = True
                    break

            # Only move horizontally if no collision
            if not collision:
                self.location[0] = new_x
        elif actual_dir[0] != 0:
            # No platforms to check, allow free movement
            self.location[0] += actual_dir[0] * self.speed * self.speed_multiplier

        # Integrated flight logic
        # Allow flight when airborne, falling (or at peak), and have flight energy
        if not self.on_ground and self.vertical_velocity <= 0 and self.flight_time_remaining > 0 and not self.needs_recharge and self.is_moving_up:
            self.can_fly = True
            self.is_currently_flying = True
        else:
            self.can_fly = False # Reset if not meeting conditions
            self.is_currently_flying = False

        if actual_dir[1] > 0:
            if self.on_ground:
                if self.can_jump:
                    self.jump()
            elif self.can_fly:
                self.location[1] += actual_dir[1] * self.speed * self.speed_multiplier
                self.vertical_velocity = 0
        elif actual_dir[1] < 0:
            if self.can_fly:
                self.location[1] += actual_dir[1] * self.speed * self.speed_multiplier
                self.vertical_velocity = 0

                # NO FLOOR BOUNDARY CHECK - allow falling through bottom
