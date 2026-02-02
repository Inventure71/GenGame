import math
import pygame
from BASE_components.BASE_effects import BaseEffect


class WaveProjectileEffect(BaseEffect):
    def __init__(
        self,
        location,
        angle,
        max_distance,
        speed,
        owner_id,
        damage,
        lifetime: float = 4.0,
    ):
        super().__init__(location)
        self.angle = angle
        self.max_distance = max_distance
        self.speed = speed
        self.owner_id = owner_id
        self.damage = damage
        self.distance_travelled = 0.0
        self.lifetime = float(lifetime)
        self.age = 0.0
        self.width = 40
        self.height = 12

    def update(self, delta_time: float) -> bool:
        step = self.speed * (delta_time * 60.0)
        dx = step * math.cos(self.angle)
        dy = step * math.sin(self.angle)
        self.location[0] += dx
        self.location[1] += dy
        self.distance_travelled += math.hypot(dx, dy)
        self.age += delta_time
        if self.distance_travelled >= self.max_distance:
            return True
        return self.age >= self.lifetime

    def get_rect(self, arena_height: float) -> pygame.Rect:
        py_x = self.location[0] - self.width / 2
        py_y = arena_height - self.location[1] - self.height / 2
        return pygame.Rect(py_x, py_y, self.width, self.height)

    def draw(self, screen: pygame.Surface, arena_height: float, camera=None):
        if not self._graphics_initialized:
            return
        if camera is not None:
            rect = camera.world_center_rect_to_screen(
                self.location[0], self.location[1], self.width, self.height
            )
        else:
            rect = self.get_rect(arena_height)
        pygame.draw.rect(screen, (150, 0, 150), rect)
        pygame.draw.rect(screen, (220, 180, 255), rect, 2)

