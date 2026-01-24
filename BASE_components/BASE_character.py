import math
import pygame
from BASE_files.BASE_network import NetworkObject


class BaseCharacter(NetworkObject):
    """Low-level character building block to be extended by GameFolder."""

    MAX_LIVES = 1

    SPEED_FAST_MIN = 7.0
    SPEED_SLOW_MAX = 1.6
    SPEED_MIN_SIZE = 9.0
    SPEED_MAX_SIZE = 120.0

    def __init__(self, name: str, description: str, image: str, location: [float, float], width: float = 30, height: float = 30):
        super().__init__()
        self.id = name
        self.name = name
        self.description = description
        self.image = image

        self.location = location
        self.width = float(width)
        self.height = float(height)

        self.speed = 3.0

        self.max_health = 100.0
        self.health = self.max_health
        self.is_alive = True

        self.lives = self.MAX_LIVES
        self.is_eliminated = False

        self.color = (220, 220, 220)
        self.last_arena_height = 900

        # Overrideable speed values for games to customize.
        self.speed_fast_min = self.SPEED_FAST_MIN
        self.speed_slow_max = self.SPEED_SLOW_MAX
        self.speed_min_size = self.SPEED_MIN_SIZE
        self.speed_max_size = self.SPEED_MAX_SIZE

        # Movement and animation state (client-side visuals).
        self.last_movement_direction = [0.0, 1.0]
        self.is_moving = False
        self.animation_frame = 0
        self.animation_timer = 0.0
        self.animation_frame_count = 0
        self.animation_speed = 0.15
        self._prev_location = list(self.location) if hasattr(self.location, "copy") else list(self.location)

        self.init_graphics()

    def __setstate__(self, state):
        self.__dict__.update(state)
        if not hasattr(self, "lives"):
            self.lives = self.MAX_LIVES
        if not hasattr(self, "is_eliminated"):
            self.is_eliminated = False
        if not hasattr(self, "animation_frame"):
            self.animation_frame = 0
        if not hasattr(self, "animation_timer"):
            self.animation_timer = 0.0
        if not hasattr(self, "animation_frame_count"):
            self.animation_frame_count = 0
        if not hasattr(self, "animation_speed"):
            self.animation_speed = 0.15
        if not hasattr(self, "_prev_location"):
            self._prev_location = list(self.location) if hasattr(self.location, "copy") else list(self.location)
        if not hasattr(self, "last_movement_direction"):
            self.last_movement_direction = [0.0, 1.0]
        if not hasattr(self, "is_moving"):
            self.is_moving = False
        self.init_graphics()

    def init_graphics(self):
        super().init_graphics()
        try:
            pygame.display.get_surface()
        except Exception:
            return

    @staticmethod
    def get_input_data(held_keys, mouse_buttons, mouse_pos):
        input_data = {
            "mouse_pos": mouse_pos,
            "held_keys": sorted(list(held_keys)),
            "mouse_buttons": list(mouse_buttons),
        }
        direction = [0, 0]
        if pygame.K_LEFT in held_keys or pygame.K_a in held_keys:
            direction[0] = -1
        if pygame.K_RIGHT in held_keys or pygame.K_d in held_keys:
            direction[0] = 1
        if pygame.K_UP in held_keys or pygame.K_w in held_keys:
            direction[1] = 1
        if pygame.K_DOWN in held_keys or pygame.K_s in held_keys:
            direction[1] = -1
        input_data["movement"] = direction
        return input_data

    def process_input(self, input_data: dict, arena):
        if not self.is_alive:
            return
        if "movement" in input_data:
            self.move(input_data["movement"], arena)
        self.handle_actions(input_data, arena)

    def handle_actions(self, input_data: dict, arena):
        """Hook for game-specific actions (abilities, pickups, etc.)."""
        return

    def update(self, delta_time: float, arena):
        if arena is None:
            self._update_client_animation(delta_time)
            return
        self.last_arena_height = arena.height
        if not getattr(arena, "headless", False):
            self._update_client_animation(delta_time)

    def get_rect(self, arena_height: float = None) -> pygame.Rect:
        if arena_height is None:
            arena_height = self.last_arena_height
        py_x = self.location[0] - self.width / 2
        py_y = arena_height - self.location[1] - self.height / 2
        return pygame.Rect(py_x, py_y, self.width, self.height)

    def get_draw_rect(self, arena_height: float = None, camera=None) -> pygame.Rect:
        if camera is not None:
            return camera.world_center_rect_to_screen(self.location[0], self.location[1], self.width, self.height)
        return self.get_rect(arena_height)

    def move(self, direction, arena):
        dx, dy = direction
        self._update_movement_state(dx, dy)
        self.location[0] += dx * self.speed
        self.location[1] += dy * self.speed
        margin_x = self.width / 2
        margin_y = self.height / 2
        self.location[0] = max(margin_x, min(arena.width - margin_x, self.location[0]))
        self.location[1] = max(margin_y, min(arena.height - margin_y, self.location[1]))

    # ---- Shared movement helpers -------------------------------------------------

    def compute_speed_for_size(self, size: float) -> float:
        """
        Shared helper for size-based speed scaling.

        Smaller characters move faster, larger characters move slower, with
        clamping so extreme sizes stay in a reasonable range.
        """
        t = (size - self.speed_min_size) / max(
            1.0, (self.speed_max_size - self.speed_min_size)
        )
        t = max(0.0, min(1.0, t))
        return self.speed_fast_min + (self.speed_slow_max - self.speed_fast_min) * t

    def _update_movement_state(self, dx: float, dy: float):
        is_moving_now = (dx != 0 or dy != 0)
        if is_moving_now:
            dist = math.hypot(dx, dy)
            if dist > 0:
                self.last_movement_direction = [dx / dist, dy / dist]
            self.is_moving = True
        else:
            self.is_moving = False

    def _update_client_animation(self, delta_time: float):
        """Client-only walking animation state."""
        if not hasattr(self, "_prev_location"):
            self._prev_location = (
                self.location.copy() if hasattr(self.location, "copy") else list(self.location)
            )

        moved = (
            abs(self.location[0] - self._prev_location[0]) > 0.01
            or abs(self.location[1] - self._prev_location[1]) > 0.01
        )
        self._prev_location = (
            self.location.copy() if hasattr(self.location, "copy") else list(self.location)
        )

        moving = bool(getattr(self, "is_moving", False)) or moved or bool(
            getattr(self, "is_eating", False)
        )
        if moving:
            self.animation_timer += delta_time
            frame_count = self.animation_frame_count if self.animation_frame_count > 0 else 1
            if self.animation_timer >= self.animation_speed:
                self.animation_timer = 0.0
                self.animation_frame = (self.animation_frame + 1) % frame_count
        else:
            self.animation_frame = 0
            self.animation_timer = 0.0

    def take_damage(self, amount: float):
        if not self.is_alive or amount <= 0:
            return
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.die()

    def heal(self, amount: float):
        if not self.is_alive:
            return
        self.health = min(self.max_health, self.health + amount)

    def die(self):
        self.is_alive = False
        self.lives -= 1
        if self.lives <= 0:
            self.is_eliminated = True

    def respawn(self, respawn_location: [float, float] = None, arena=None):
        if self.is_eliminated:
            return
        if respawn_location:
            self.location = respawn_location.copy()
        self.health = self.max_health
        self.is_alive = True

    def draw(self, screen: pygame.Surface, arena_height: float = None, camera=None):
        if not self._graphics_initialized:
            return
        rect = self.get_draw_rect(arena_height, camera)
        color = self.color if self.is_alive else (120, 120, 120)
        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, (30, 30, 30), rect, 2)

        health_ratio = self.health / max(1.0, self.max_health)
        bar_width = self.width
        bar_height = 6
        bar_x = rect.x
        bar_y = rect.y - 10
        pygame.draw.rect(screen, (60, 60, 60), (bar_x, bar_y, bar_width, bar_height))
        pygame.draw.rect(screen, (80, 220, 80), (bar_x, bar_y, bar_width * health_ratio, bar_height))
