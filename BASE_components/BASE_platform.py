import pygame
from BASE_components.BASE_network import NetworkObject

class BasePlatform(NetworkObject):
    def __init__(self, x: float, y: float, width: float, height: float, color=(100, 100, 100), health: float = 100.0):
        # Initialize network capabilities first
        super().__init__()
        self._set_network_identity("BASE_components.BASE_platform", "BasePlatform")

        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.health = health
        self.is_destroyed = False

        # Store width and height as attributes for serialization
        self.width = width
        self.height = height

        # Physics properties (moved from GAME_platform for compatibility)
        self.float_x = float(x)
        self.float_y = float(y)
        self.original_x = float(x)
        self.original_y = float(y)
        self.being_pulled = False

        # Initialize graphics (can be called later for headless mode)
        self.init_graphics()

    def init_graphics(self):
        """
        Initialize graphics resources.
        Safe to call multiple times and works even if pygame is not initialized.
        Thread-safe for testing scenarios.
        """
        super().init_graphics()

        # Skip pygame operations if we're in a thread other than the main thread
        # or if pygame operations might cause issues (like during testing)
        try:
            import threading
            if threading.current_thread() != threading.main_thread():
                # We're in a background thread, skip pygame operations
                # But still reconstruct rect if needed for functionality
                if not hasattr(self, 'rect') or self.rect is None:
                    # Create a mock rect for non-pygame usage
                    class MockRect:
                        def __init__(self, x, y, w, h):
                            self.x, self.y, self.width, self.height = x, y, w, h
                    self.rect = MockRect(int(self.float_x), int(self.float_y), int(self.width), int(self.height))
                return

            # Reconstruct rect from stored position data if it's missing (after deserialization)
            if not hasattr(self, 'rect') or self.rect is None:
                self.rect = pygame.Rect(int(self.float_x), int(self.float_y), int(self.width), int(self.height))

            # Only initialize pygame-dependent graphics if pygame is available
            # and we're in the main thread
            pygame.display.get_surface()
            # If we get here, pygame is initialized - additional setup if needed
            pass
        except:
            # Pygame not initialized or no display - skip graphics initialization
            # But still provide basic rect functionality
            if not hasattr(self, 'rect') or self.rect is None:
                try:
                    self.rect = pygame.Rect(int(self.float_x), int(self.float_y), int(self.width), int(self.height))
                except:
                    # If pygame.Rect fails, create a mock
                    class MockRect:
                        def __init__(self, x, y, w, h):
                            self.x, self.y, self.width, self.height = x, y, w, h
                    self.rect = MockRect(int(self.float_x), int(self.float_y), int(self.width), int(self.height))

    def move(self, dx: float, dy: float):
        """Move the platform by [dx, dy]."""
        self.float_x += dx
        self.float_y += dy
        self.rect.x = int(self.float_x)
        self.rect.y = int(self.float_y)

    def return_to_origin(self, delta_time: float, return_speed: float = 100.0):
        """Gradually move back to original position."""
        import math
        dx = self.original_x - self.float_x
        dy = self.original_y - self.float_y
        dist = math.hypot(dx, dy)

        if dist > 0.5:
            move_dist = min(dist, return_speed * delta_time)
            self.move((dx / dist) * move_dist, (dy / dist) * move_dist)
        else:
            self.float_x = self.original_x
            self.float_y = self.original_y
            self.rect.x = int(self.float_x)
            self.rect.y = int(self.float_y)

    def take_damage(self, amount: float):
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.is_destroyed = True

    def draw(self, screen: pygame.Surface, arena_height: float = None, camera=None):
        if self.is_destroyed or not self._graphics_initialized:
            return
        pygame.draw.rect(screen, self.color, self.rect)


class BaseWorldPlatform(BasePlatform):
    """World-space platform that converts to screen-space for rendering."""

    def __init__(
        self,
        center_x: float,
        center_y: float,
        width: float,
        height: float,
        arena_height: float,
        color=(100, 100, 100),
        health: float = 100.0,
    ):
        self.world_center = [center_x, center_y]
        self.last_arena_height = arena_height
        py_x = center_x - width / 2
        py_y = arena_height - center_y - height / 2
        super().__init__(py_x, py_y, width, height, color=color, health=health)

    def get_draw_rect(self, arena_height: float = None, camera=None) -> pygame.Rect:
        if arena_height is None:
            arena_height = self.last_arena_height
        else:
            self.last_arena_height = arena_height
        if camera is not None:
            return camera.world_center_rect_to_screen(
                self.world_center[0],
                self.world_center[1],
                self.width,
                self.height,
            )
        py_x = self.world_center[0] - self.width / 2
        py_y = arena_height - self.world_center[1] - self.height / 2
        return pygame.Rect(py_x, py_y, self.width, self.height)
