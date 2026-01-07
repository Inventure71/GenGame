from BASE_components.BASE_character import BaseCharacter
import pygame

class Character(BaseCharacter):
    """
    GAME implementation of Character. 
    Inherits improved movement and flight from BaseCharacter.
    """
    def __init__(self, name: str, description: str, image: str, location: [float, float], width: float = 50, height: float = 50):
        super().__init__(name, description, image, location, width, height)
        self.speed = 6.0
        self.color = (255, 255, 0) # Yellow
        
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

        # Health bar
        health_bar_width = self.width * self.scale_ratio
        health_ratio = self.health / self.max_health
        pygame.draw.rect(screen, (255, 0, 0), (self.location[0], py_y - 10, health_bar_width, 5))
        pygame.draw.rect(screen, (0, 255, 0), (self.location[0], py_y - 10, health_bar_width * health_ratio, 5))

        # Flight bar (UI feedback on the character)
        flight_ratio = self.flight_time_remaining / self.max_flight_time
        bar_color = (0, 191, 255) if not self.needs_recharge else (100, 100, 100)
        pygame.draw.rect(screen, (40, 40, 40), (self.location[0], py_y - 16, health_bar_width, 4))
        pygame.draw.rect(screen, bar_color, (self.location[0], py_y - 16, health_bar_width * flight_ratio, 4))
