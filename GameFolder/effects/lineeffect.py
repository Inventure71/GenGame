import math
import pygame
from BASE_components.BASE_effects import TimedEffect


class LineEffect(TimedEffect):
    def __init__(
        self,
        location,
        angle,
        length,
        width,
        owner_id,
        damage,
        damage_cooldown,
        knockback_distance: float = 0.0,
        lifetime: float = 0.5,
    ):
        super().__init__(location, lifetime)
        self.angle = angle
        self.length = length
        self.width = width
        self.owner_id = owner_id
        self.damage = damage
        self.damage_cooldown = damage_cooldown
        self.knockback_distance = knockback_distance

    def draw(self, screen: pygame.Surface, arena_height: float, camera=None):
        if not self._graphics_initialized:
            return
        start = (self.location[0], self.location[1])
        end = (
            self.location[0] + self.length * math.cos(self.angle),
            self.location[1] + self.length * math.sin(self.angle),
        )
        if camera is not None:
            start_py = camera.world_to_screen_point(start[0], start[1])
            end_py = camera.world_to_screen_point(end[0], end[1])
        else:
            start_py = (int(start[0]), int(arena_height - start[1]))
            end_py = (int(end[0]), int(arena_height - end[1]))
        pygame.draw.line(screen, (255, 255, 255), start_py, end_py, int(self.width))

