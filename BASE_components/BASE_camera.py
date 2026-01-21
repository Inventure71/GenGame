import pygame


class BaseCamera:
    """World-to-screen camera for large arenas (world coords y-up, screen y-down)."""

    def __init__(self, world_width: float, world_height: float, view_width: float, view_height: float):
        self.world_width = float(world_width)
        self.world_height = float(world_height)
        self.view_width = float(view_width)
        self.view_height = float(view_height)
        self.center = [self.world_width / 2, self.world_height / 2]
        self._clamp_center()

    def set_world_size(self, world_width: float, world_height: float):
        self.world_width = float(world_width)
        self.world_height = float(world_height)
        self._clamp_center()

    def set_view_size(self, view_width: float, view_height: float):
        self.view_width = float(view_width)
        self.view_height = float(view_height)
        self._clamp_center()

    def set_center(self, x: float, y: float):
        self.center[0] = float(x)
        self.center[1] = float(y)
        self._clamp_center()

    def _clamp_center(self):
        half_w = self.view_width / 2
        half_h = self.view_height / 2

        if self.world_width <= self.view_width:
            self.center[0] = self.world_width / 2
        else:
            self.center[0] = max(half_w, min(self.world_width - half_w, self.center[0]))

        if self.world_height <= self.view_height:
            self.center[1] = self.world_height / 2
        else:
            self.center[1] = max(half_h, min(self.world_height - half_h, self.center[1]))

    def get_viewport(self):
        left = self.center[0] - self.view_width / 2
        bottom = self.center[1] - self.view_height / 2
        return left, bottom, left + self.view_width, bottom + self.view_height

    def world_to_screen_point(self, world_x: float, world_y: float):
        left, bottom, _, top = self.get_viewport()
        screen_x = world_x - left
        screen_y = top - world_y
        return screen_x, screen_y

    def screen_to_world_point(self, screen_x: float, screen_y: float):
        left, bottom, _, top = self.get_viewport()
        world_x = screen_x + left
        world_y = top - screen_y
        return world_x, world_y

    def world_center_rect_to_screen(self, center_x: float, center_y: float, width: float, height: float) -> pygame.Rect:
        screen_x, screen_y = self.world_to_screen_point(center_x, center_y)
        return pygame.Rect(screen_x - width / 2, screen_y - height / 2, width, height)
