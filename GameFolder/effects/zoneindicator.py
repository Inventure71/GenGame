import pygame
from BASE_components.BASE_effects import BaseEffect


class ZoneIndicator(BaseEffect):
    def __init__(self, center, radius):
        super().__init__(center)
        self.radius = radius
        self.always_visible = True

    def update_from_safe_zone(self, center, radius):
        self.location = center
        self.radius = radius

    def draw(self, screen: pygame.Surface, arena_height: float, camera=None):
        if not self._graphics_initialized:
            return
        if camera is not None:
            center = camera.world_to_screen_point(self.location[0], self.location[1])
            center = (int(center[0]), int(center[1]))
            screen_width = screen.get_width()
            screen_height = screen.get_height()
        else:
            center = (int(self.location[0]), int(arena_height - self.location[1]))
            screen_width = screen.get_width()
            screen_height = screen.get_height()
        
        # Draw the safe zone as a purple circle outline (border)
        pygame.draw.circle(screen, (128, 0, 128), center, int(self.radius), 3)
        
        # Create a transparent purple overlay for the outside area
        overlay = pygame.Surface((screen_width, screen_height))
        # Fill entire overlay with semi-transparent purple
        overlay.fill((128, 0, 128))
        overlay.set_alpha(100)  # Set overall transparency
        
        # Draw a white circle where the safe zone is (this will be made transparent)
        pygame.draw.circle(overlay, (255, 255, 255), center, int(self.radius))
        
        # Set white as the colorkey (transparent color) - this makes the inside transparent
        overlay.set_colorkey((255, 255, 255))
        
        # Blit the overlay onto the screen (only outside the circle will show purple)
        screen.blit(overlay, (0, 0))
