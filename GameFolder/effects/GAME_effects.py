import math
import pygame
from BASE_components.BASE_effects import BaseEffect, TimedEffect


class ConeEffect(TimedEffect):
    def __init__(self, location, angle, height, base, owner_id, damage, damage_cooldown, slow_multiplier=0.6, lifetime=0.7):
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


class RadialEffect(TimedEffect):
    def __init__(self, location, radius, owner_id, damage, damage_cooldown, knockback_distance=0.0, lifetime=0.5):
        super().__init__(location, lifetime)
        self.radius = radius
        self.owner_id = owner_id
        self.damage = damage
        self.damage_cooldown = damage_cooldown
        self.knockback_distance = knockback_distance

    def draw(self, screen: pygame.Surface, arena_height: float, camera=None):
        if not self._graphics_initialized:
            return
        if camera is not None:
            center = camera.world_to_screen_point(self.location[0], self.location[1])
            center = (int(center[0]), int(center[1]))
        else:
            center = (int(self.location[0]), int(arena_height - self.location[1]))
        pygame.draw.circle(screen, (255, 255, 255), center, int(self.radius), 2)


class LineEffect(TimedEffect):
    def __init__(self, location, angle, length, width, owner_id, damage, damage_cooldown, knockback_distance=0.0, lifetime=0.5):
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


class WaveProjectileEffect(BaseEffect):
    def __init__(self, location, angle, max_distance, speed, owner_id, damage, lifetime=4.0):
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
            rect = camera.world_center_rect_to_screen(self.location[0], self.location[1], self.width, self.height)
        else:
            rect = self.get_rect(arena_height)
        pygame.draw.rect(screen, (150, 0, 150), rect)
        pygame.draw.rect(screen, (220, 180, 255), rect, 2)


class ObstacleEffect(TimedEffect):
    def __init__(self, location, size, owner_id, mine=False, wall=False, lifetime=10.0):
        super().__init__(location, lifetime)
        self.size = size
        self.owner_id = owner_id
        self.mine = mine
        self.wall = wall

    def get_rect(self, arena_height: float) -> pygame.Rect:
        py_x = self.location[0] - self.size / 2
        py_y = arena_height - self.location[1] - self.size / 2
        return pygame.Rect(py_x, py_y, self.size, self.size)

    def draw(self, screen: pygame.Surface, arena_height: float, camera=None):
        if not self._graphics_initialized:
            return
        if camera is not None:
            rect = camera.world_center_rect_to_screen(self.location[0], self.location[1], self.size, self.size)
        else:
            rect = self.get_rect(arena_height)
        color = (110, 70, 20) if not self.wall else (90, 60, 15)
        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, (60, 40, 10), rect, 2)
        if self.mine:
            pygame.draw.circle(screen, (200, 80, 0), rect.center, max(2, int(self.size / 6)))


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
