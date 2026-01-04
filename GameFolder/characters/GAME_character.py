from BASE_components.BASE_character import BaseCharacter
import pygame

class Character(BaseCharacter):
    def __init__(self, name: str, description: str, image: str, location: [float, float], width: float = 50, height: float = 50):
        super().__init__(name, description, image, location, width, height)
        # EXAMPLE: Increase base speed for this specific character class
        self.speed = 6.0
        self.color = (255, 255, 0) # Yellow color
        
        # No initial weapon - must pick up from the ground!
        
        # Flight Mechanic
        self.max_flight_time = 3.0
        self.flight_time_remaining = self.max_flight_time
        self.needs_recharge = False
        self.is_currently_flying = False
        self.physics_inverted = False
        self.last_target = [0, 0]

    def shoot(self, target_pos: [float, float]):
        if not self.is_alive or not self.weapon:
            return None

        self.last_target = target_pos

        # Center of character
        start_x = self.location[0] + (self.width * self.scale_ratio) / 2
        start_y = self.location[1] + (self.height * self.scale_ratio) / 2

        return self.weapon.shoot(start_x, start_y, target_pos[0], target_pos[1], self.id)

    def secondary_fire(self, target_pos: [float, float]):
        if not self.is_alive or not self.weapon:
            return None
        self.last_target = target_pos
        start_x = self.location[0] + (self.width * self.scale_ratio) / 2
        start_y = self.location[1] + (self.height * self.scale_ratio) / 2
        return self.weapon.secondary_fire(start_x, start_y, target_pos[0], target_pos[1], self.id)

    def special_fire(self, target_pos: [float, float], is_holding: bool):
        if not self.is_alive or not self.weapon:
            return None
        self.last_target = target_pos
        start_x = self.location[0] + (self.width * self.scale_ratio) / 2
        start_y = self.location[1] + (self.height * self.scale_ratio) / 2
        return self.weapon.special_fire(start_x, start_y, target_pos[0], target_pos[1], self.id, is_holding)

    def move(self, direction: [float, float], platforms: list = None):
        if self.physics_inverted:
            direction[0] *= -1
            direction[1] *= -1

        # Determine if we want to fly
        # If in air and moving vertically, attempt to fly
        if not self.on_ground and abs(direction[1]) > 0 and self.flight_time_remaining > 0 and not self.needs_recharge:
            self.can_fly = True
            self.is_currently_flying = True
        else:
            self.can_fly = False
            self.is_currently_flying = False
            
        super().move(direction, platforms)

    def update(self, delta_time: float, platforms=None, arena_height=600):
        self.physics_inverted = False
        # Recharge logic
        if self.on_ground:
            self.flight_time_remaining = min(self.max_flight_time, self.flight_time_remaining + delta_time * 1.5)
            if self.flight_time_remaining >= self.max_flight_time:
                self.needs_recharge = False
        
        # Fuel consumption
        if self.is_currently_flying and not self.on_ground:
            self.flight_time_remaining -= delta_time
            if self.flight_time_remaining <= 0:
                self.flight_time_remaining = 0
                self.needs_recharge = True
                self.can_fly = False
                self.is_currently_flying = False

        super().update(delta_time, platforms, arena_height)

        if not self.is_alive:
            return

        # Gradually recover multipliers
        if self.speed_multiplier < 1.0:
            self.speed_multiplier = min(1.0, self.speed_multiplier + 0.5 * delta_time)

        if self.jump_height_multiplier < 1.0:
            self.jump_height_multiplier = min(1.0, self.jump_height_multiplier + 0.5 * delta_time)

    def draw(self, screen: pygame.Surface, arena_height: float):
        if not self.is_alive:
            return

        # Map y-up to pygame y-down
        py_y = arena_height - self.location[1] - (self.height * self.scale_ratio)
        py_rect = pygame.Rect(self.location[0], py_y, self.width * self.scale_ratio, self.height * self.scale_ratio)

        # Draw with custom color instead of base green
        draw_color = self.color
        if self.is_currently_flying:
            # Blue tint for flying
            draw_color = (min(255, self.color[0] + 50), min(255, self.color[1] + 50), 255)
        
        pygame.draw.rect(screen, draw_color, py_rect)

        # Draw health bar
        health_bar_width = self.width * self.scale_ratio
        health_ratio = self.health / self.max_health
        pygame.draw.rect(screen, (255, 0, 0), (self.location[0], py_y - 10, health_bar_width, 5))
        pygame.draw.rect(screen, (0, 255, 0), (self.location[0], py_y - 10, health_bar_width * health_ratio, 5))

        # Draw flight bar
        flight_ratio = self.flight_time_remaining / self.max_flight_time
        bar_color = (0, 191, 255) if not self.needs_recharge else (100, 100, 100)
        pygame.draw.rect(screen, (40, 40, 40), (self.location[0], py_y - 16, health_bar_width, 4))
        pygame.draw.rect(screen, bar_color, (self.location[0], py_y - 16, health_bar_width * flight_ratio, 4))