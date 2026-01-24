import math
import pygame
from typing import Dict, List
from BASE_components.BASE_character import BaseCharacter
from BASE_components.BASE_platform import BasePlatform
from BASE_components.BASE_effects import BaseEffect
from BASE_components.BASE_safe_zone import SafeZone


WORLD_WIDTH = 2800 # DO NOT MANUALLY CHANGE THESE VALUES, NO MATTER WHAT THE INSTRUCTIONS ARE.
WORLD_HEIGHT = 1800 # DO NOT MANUALLY CHANGE THESE VALUES, NO MATTER WHAT THE INSTRUCTIONS ARE.

class Arena:
    """Immutable game loop and safe zone management. Extend for game logic."""

    TICK_RATE = 60

    def __init__(self, width: int = 1400, height: int = 900, headless: bool = False):
        self.headless = headless
        self.width = width
        self.height = height

        if not self.headless:
            pygame.init()
            self.screen = pygame.display.set_mode((self.width, self.height),pygame.FULLSCREEN)
            pygame.display.set_caption("Core Arena")
            self.clock = pygame.time.Clock()
        else:
            self.screen = None
            self.clock = None

        self.running = True

        self.characters: List[BaseCharacter] = []
        self.platforms: List[BasePlatform] = []
        self.effects: List[BaseEffect] = []
        self.projectiles = []
        self.weapon_pickups = []
        self.ammo_pickups = []

        self.held_keycodes = set()

        self.game_over = False
        self.winner = None
        self.respawn_timer: Dict[str, float] = {}
        self.respawn_delay = 0.0
        self.allow_respawn = False

        self.tick_accumulator = 0.0
        self.tick_interval = 1.0 / self.TICK_RATE
        self.current_time = 0.0

        self.safe_zone = SafeZone(width, height)
        self.enable_safe_zone = True
        self.safe_damage_times = {}
        self.safe_damage_interval = 1.0

    def add_character(self, character: BaseCharacter):
        self.characters.append(character)

    def add_platform(self, platform: BasePlatform):
        self.platforms.append(platform)

    def add_effect(self, effect: BaseEffect):
        self.effects.append(effect)

    def update(self, delta_time: float):
        self.current_time += delta_time
        if self.enable_safe_zone:
            self.safe_zone.update(delta_time)

        self._update_effects(delta_time)

        for char in self.characters:
            char.update(delta_time, self)

        if self.enable_safe_zone:
            self._apply_safe_zone_damage()

        self.handle_collisions()

        if self.allow_respawn:
            self.handle_respawns(delta_time)

        self.check_winner()

    def _update_effects(self, delta_time: float):
        active = []
        for effect in self.effects:
            expired = False
            if hasattr(effect, "update"):
                expired = effect.update(delta_time)
            if not expired:
                active.append(effect)
        self.effects = active

    def _apply_safe_zone_damage(self):
        for char in self.characters:
            if not char.is_alive:
                continue
            if not self.safe_zone.contains(char.location[0], char.location[1]):
                last = self.safe_damage_times.get(char.id, 0.0)
                if self.current_time - last >= self.safe_damage_interval:
                    char.take_damage(self.safe_zone.damage)
                    self.safe_damage_times[char.id] = self.current_time

    def handle_collisions(self):
        """Override in GameFolder for game-specific collisions."""
        return

    def handle_respawns(self, delta_time: float):
        for char in self.characters:
            if not char.is_alive and not char.is_eliminated:
                if char.id not in self.respawn_timer:
                    self.respawn_timer[char.id] = self.respawn_delay
                self.respawn_timer[char.id] -= delta_time
                if self.respawn_timer[char.id] <= 0:
                    respawn_x = self.width / 2
                    respawn_y = self.height / 2
                    char.respawn([respawn_x, respawn_y], self)
                    del self.respawn_timer[char.id]

    def check_winner(self):
        if self.game_over:
            return
        alive = [char for char in self.characters if not char.is_eliminated]
        if len(alive) == 1:
            self.winner = alive[0]
            self.game_over = True
        elif len(alive) == 0:
            self.game_over = True

    def _apply_knockback(self, cow, source_location, distance):
        dx = cow.location[0] - source_location[0]
        dy = cow.location[1] - source_location[1]
        dist = math.hypot(dx, dy)
        if dist == 0:
            return
        cow.location[0] += (dx / dist) * distance
        cow.location[1] += (dy / dist) * distance
        margin = cow.size / 2
        cow.location[0] = max(margin, min(self.width - margin, cow.location[0]))
        cow.location[1] = max(margin, min(self.height - margin, cow.location[1]))

    def _push_out_of_rect(self, cow, obstacle_rect: pygame.Rect):
        cow_rect = cow.get_rect(self.height)
        overlap_x = cow_rect.width / 2 + obstacle_rect.width / 2 - abs(
            cow_rect.centerx - obstacle_rect.centerx
        )
        overlap_y = cow_rect.height / 2 + obstacle_rect.height / 2 - abs(
            cow_rect.centery - obstacle_rect.centery
        )
        if overlap_x < overlap_y:
            if cow_rect.centerx < obstacle_rect.centerx:
                cow.location[0] -= overlap_x
            else:
                cow.location[0] += overlap_x
        else:
            if cow_rect.centery < obstacle_rect.centery:
                cow.location[1] += overlap_y
            else:
                cow.location[1] -= overlap_y

    @staticmethod
    def _circle_intersects_circle(circle1_center, circle1_radius, circle2_center, circle2_radius) -> bool:
        dx = circle1_center[0] - circle2_center[0]
        dy = circle1_center[1] - circle2_center[1]
        dist_sq = dx * dx + dy * dy
        radius_sum = circle1_radius + circle2_radius
        return dist_sq <= radius_sum * radius_sum

    @staticmethod
    def _circle_intersects_triangle(circle_center, circle_radius, triangle_points) -> bool:
        (x1, y1), (x2, y2), (x3, y3) = triangle_points
        cx, cy = circle_center

        denom = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if denom != 0:
            a = ((y2 - y3) * (cx - x3) + (x3 - x2) * (cy - y3)) / denom
            b = ((y3 - y1) * (cx - x3) + (x1 - x3) * (cy - y3)) / denom
            c = 1 - a - b
            if 0 <= a <= 1 and 0 <= b <= 1 and 0 <= c <= 1:
                return True

        edges = [
            ((x1, y1), (x2, y2)),
            ((x2, y2), (x3, y3)),
            ((x3, y3), (x1, y1)),
        ]
        for (p1x, p1y), (p2x, p2y) in edges:
            dx = p2x - p1x
            dy = p2y - p1y
            line_len_sq = dx * dx + dy * dy
            if line_len_sq == 0:
                dist = math.hypot(cx - p1x, cy - p1y)
                if dist <= circle_radius:
                    return True
            else:
                t = max(0, min(1, ((cx - p1x) * dx + (cy - p1y) * dy) / line_len_sq))
                proj_x = p1x + t * dx
                proj_y = p1y + t * dy
                dist = math.hypot(cx - proj_x, cy - proj_y)
                if dist <= circle_radius:
                    return True

        return False

    @staticmethod
    def _circle_intersects_line(circle_center, circle_radius, line_start, angle, length, width) -> bool:
        cx, cy = circle_center
        line_end = (
            line_start[0] + length * math.cos(angle),
            line_start[1] + length * math.sin(angle),
        )

        dx = line_end[0] - line_start[0]
        dy = line_end[1] - line_start[1]
        line_len_sq = dx * dx + dy * dy

        if line_len_sq == 0:
            dist = math.hypot(cx - line_start[0], cy - line_start[1])
            return dist <= circle_radius + width / 2

        t = max(0, min(1, ((cx - line_start[0]) * dx + (cy - line_start[1]) * dy) / line_len_sq))
        proj_x = line_start[0] + t * dx
        proj_y = line_start[1] + t * dy

        dist_to_line = math.hypot(cx - proj_x, cy - proj_y)
        return dist_to_line <= (width / 2) + circle_radius

    def render(self):
        if self.headless:
            return
        # Additional safety check: ensure screen exists
        if self.screen is None:
            return
        camera = getattr(self, "camera", None)
        self.screen.fill((30, 30, 30))
        for platform in self.platforms:
            platform.draw(self.screen, self.height, camera=camera)
        for effect in self.effects:
            if hasattr(effect, "draw"):
                effect.draw(self.screen, self.height, camera=camera)
        for pickup in self.weapon_pickups:
            pickup.draw(self.screen, self.height, camera=camera)
        for char in self.characters:
            char.draw(self.screen, self.height, camera=camera)
        try:
            pygame.display.flip()
        except pygame.error as e:
            print(f"Error flipping display: {e}")
            if "GL context" not in str(e) and "BadAccess" not in str(e):
                raise  # Re-raise if it's a different error

    def _capture_input(self):
        if self.headless:
            return
        pygame.event.pump()
        mx, my = pygame.mouse.get_pos()
        camera = getattr(self, "camera", None)
        if camera is not None:
            world_mx, world_my = camera.screen_to_world_point(mx, my)
        else:
            world_mx, world_my = mx, self.height - my
        pressed = pygame.mouse.get_pressed()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.held_keycodes.add(event.key)
                if event.key == pygame.K_ESCAPE:
                    self.running = False
            elif event.type == pygame.KEYUP:
                self.held_keycodes.discard(event.key)

        if self.characters:
            char = self.characters[0]
            if char.is_alive:
                input_data = char.get_input_data(self.held_keycodes, pressed, [world_mx, world_my])
                char.process_input(input_data, self)

    def step(self):
        if self.headless:
            frame_delta = 1.0 / self.TICK_RATE
        else:
            frame_delta = self.clock.tick(60) / 1000.0

        if not self.headless:
            self._capture_input()

        self.update(frame_delta)
        self.render()

    def run(self):
        while self.running:
            self.step()
        pygame.quit()
