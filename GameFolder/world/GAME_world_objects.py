import pygame
from BASE_components.BASE_platform import BasePlatform


class WorldObstacle(BasePlatform):
    def __init__(self, center_x: float, center_y: float, size: float, obstacle_type: str, arena_height: float):
        self.world_center = [center_x, center_y]
        self.size = size
        self.obstacle_type = obstacle_type

        py_x = center_x - size / 2
        py_y = arena_height - center_y - size / 2

        color = (80, 80, 80) if obstacle_type == "blocking" else (60, 120, 160)
        super().__init__(py_x, py_y, size, size, color=color)
        self._set_network_identity("GameFolder.world.GAME_world_objects", "WorldObstacle")

    def draw(self, screen: pygame.Surface, arena_height: float = None, camera=None):
        if self.is_destroyed or not self._graphics_initialized:
            return
        color = (90, 90, 90) if self.obstacle_type == "blocking" else (70, 140, 180)
        if camera is not None:
            rect = camera.world_center_rect_to_screen(self.world_center[0], self.world_center[1], self.size, self.size)
        else:
            rect = self.rect
        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, (30, 30, 30), rect, 2)


class GrassField(BasePlatform):
    def __init__(self, center_x: float, center_y: float, radius: float, max_food: float, arena_height: float):
        self.world_center = [center_x, center_y]
        self.radius = radius
        self.max_food = max_food
        self.current_food = max_food

        py_x = center_x - radius
        py_y = arena_height - center_y - radius

        super().__init__(py_x, py_y, radius * 2, radius * 2, color=(40, 160, 40))
        self._set_network_identity("GameFolder.world.GAME_world_objects", "GrassField")

    def can_eat(self, cow_x: float, cow_y: float, cow_radius: float) -> bool:
        dx = cow_x - self.world_center[0]
        dy = cow_y - self.world_center[1]
        return (dx * dx + dy * dy) <= (self.radius + cow_radius) ** 2

    def eat(self) -> bool:
        if self.current_food > 0:
            self.current_food -= 1
            return True
        return False

    def regrow(self, delta_time: float, rate: float = 0.2):
        if self.current_food < self.max_food:
            self.current_food = min(self.max_food, self.current_food + rate * delta_time)

    def draw(self, screen: pygame.Surface, arena_height: float = None, camera=None):
        if self.is_destroyed or not self._graphics_initialized:
            return
        fullness = self.current_food / max(1.0, self.max_food)
        color = (40, int(120 + 100 * fullness), 40)
        if camera is not None:
            center = camera.world_to_screen_point(self.world_center[0], self.world_center[1])
            center = (int(center[0]), int(center[1]))
        else:
            center = (int(self.world_center[0]), int(arena_height - self.world_center[1]))
        pygame.draw.circle(screen, color, center, int(self.radius))
        pygame.draw.circle(screen, (20, 60, 20), center, int(self.radius), 2)
