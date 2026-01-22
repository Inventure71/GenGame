import pygame
import random
from BASE_components.BASE_platform import BasePlatform
from BASE_components.BASE_asset_handler import AssetHandler

class WorldObstacle(BasePlatform):
    def __init__(self, center_x: float, center_y: float, size: float, obstacle_type: str, arena_height: float):
        self.world_center = [center_x, center_y]
        self.size = size
        self.obstacle_type = obstacle_type
        self._anim_offset = random.randint(0, 1000)

        py_x = center_x - size / 2
        py_y = arena_height - center_y - size / 2

        color = (80, 80, 80) if obstacle_type == "blocking" else (60, 120, 160)
        super().__init__(py_x, py_y, size, size, color=color)
        self._set_network_identity("GameFolder.world.GAME_world_objects", "WorldObstacle")

    def draw(self, screen: pygame.Surface, arena_height: float = None, camera=None):
        if self.is_destroyed or not self._graphics_initialized:
            return
        if camera is not None:
            rect = camera.world_center_rect_to_screen(self.world_center[0], self.world_center[1], self.size, self.size)
        else:
            rect = self.rect

        if self.obstacle_type == "slowing":
            def fallback(surface):
                surface.fill((70, 140, 180))
                pygame.draw.rect(surface, (30, 60, 80), surface.get_rect(), 2)

            frames, _ = AssetHandler.get_animation(
                "ACQUA_",
                5,
                size=(int(rect.width), int(rect.height)),
                fallback_draw=fallback,
            )
            if frames:
                tick = pygame.time.get_ticks() if pygame.get_init() else 0
                frame_index = int((tick / 120) + self._anim_offset) % len(frames)
                screen.blit(frames[frame_index], rect)
            return

        color = (90, 90, 90)

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
        bucket = max(0, min(10, int(fullness * 10)))

        if camera is not None:
            rect = camera.world_center_rect_to_screen(self.world_center[0], self.world_center[1], self.radius * 2, self.radius * 2)
        else:
            rect = pygame.Rect(
                self.world_center[0] - self.radius,
                arena_height - self.world_center[1] - self.radius,
                self.radius * 2,
                self.radius * 2,
            )
        def fallback(surface):
            center = (surface.get_width() // 2, surface.get_height() // 2)
            radius = min(center[0], center[1])
            color = (40, int(120 + 100 * fullness), 40)
            pygame.draw.circle(surface, color, center, radius)
            pygame.draw.circle(surface, (20, 60, 20), center, radius, 2)

        grass_surface, loaded = AssetHandler.get_image(
            "ERBA.png",
            size=(int(rect.width), int(rect.height)),
            fallback_draw=fallback,
            fallback_tag=f"fullness_{bucket}",
        )
        if grass_surface is None:
            return
        if loaded and fullness < 1.0:
            grass_surface, _ = AssetHandler.get_image_with_alpha(
                "ERBA.png",
                size=(int(rect.width), int(rect.height)),
                alpha=int(120 + 120 * (bucket / 10.0)),
                fallback_draw=None,
                fallback_tag=None,
            )
        screen.blit(grass_surface, rect)
