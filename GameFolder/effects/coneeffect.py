import math
import pygame
from BASE_components.BASE_effects import TimedEffect


class ConeEffect(TimedEffect):
    def __init__(
        self,
        location,
        angle,
        height,
        base,
        owner_id,
        damage,
        damage_cooldown,
        slow_multiplier=0.6,
        lifetime=0.7,
    ):
        super().__init__(location, lifetime)
        self.angle = angle
        self.height = height
        self.base = base
        self.owner_id = owner_id
        self.damage = damage
        self.damage_cooldown = damage_cooldown
        self.slow_multiplier = slow_multiplier

    def get_triangle_points(self):
        p1_x, p1_y = self.location[0], self.location[1]
        p2_x = p1_x + self.height * math.cos(self.angle)
        p2_y = p1_y + self.height * math.sin(self.angle)
        p3_x = p2_x - self.base * 0.5 * math.sin(self.angle)
        p3_y = p2_y + self.base * 0.5 * math.cos(self.angle)
        p4_x = p2_x + self.base * 0.5 * math.sin(self.angle)
        p4_y = p2_y - self.base * 0.5 * math.cos(self.angle)
        return (p1_x, p1_y), (p3_x, p3_y), (p4_x, p4_y)

    def draw(self, screen: pygame.Surface, arena_height: float, camera=None):
        if not self._graphics_initialized:
            return
        p1, p3, p4 = self.get_triangle_points()
        if camera is not None:
            points = [
                camera.world_to_screen_point(p1[0], p1[1]),
                camera.world_to_screen_point(p3[0], p3[1]),
                camera.world_to_screen_point(p4[0], p4[1]),
            ]
        else:
            points = [
                (p1[0], arena_height - p1[1]),
                (p3[0], arena_height - p3[1]),
                (p4[0], arena_height - p4[1]),
            ]
        pygame.draw.polygon(screen, (240, 240, 255), points, 0)
        pygame.draw.polygon(screen, (200, 200, 255), points, 2)

