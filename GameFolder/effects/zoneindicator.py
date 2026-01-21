import pygame
from BASE_components.BASE_effects import BaseEffect


class ZoneIndicator(BaseEffect):
    def __init__(self, center, radius):
        super().__init__(center)
        self.radius = radius

    def update_from_safe_zone(self, center, radius):
        self.location = center
        self.radius = radius

    def draw(self, screen: pygame.Surface, arena_height: float, camera=None):
        if not self._graphics_initialized:
            return
        if camera is not None:
            center = camera.world_to_screen_point(self.location[0], self.location[1])
            center = (int(center[0]), int(center[1]))
        else:
            center = (int(self.location[0]), int(arena_height - self.location[1]))
        pygame.draw.circle(screen, (255, 50, 50), center, int(self.radius), 2)

