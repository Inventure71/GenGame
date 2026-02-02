import pygame
from BASE_components.BASE_effects import TimedEffect


class ObstacleEffect(TimedEffect):
    def __init__(
        self,
        location,
        size,
        owner_id,
        mine: bool = False,
        wall: bool = False,
        lifetime: float = 10.0,
    ):
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
            rect = camera.world_center_rect_to_screen(
                self.location[0], self.location[1], self.size, self.size
            )
        else:
            rect = self.get_rect(arena_height)
        color = (110, 70, 20) if not self.wall else (90, 60, 15)
        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, (60, 40, 10), rect, 2)
        if self.mine:
            pygame.draw.circle(
                screen, (200, 80, 0), rect.center, max(2, int(self.size / 6))
            )

