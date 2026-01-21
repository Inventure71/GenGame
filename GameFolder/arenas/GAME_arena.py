import math
import random
import pygame
from BASE_components.BASE_arena import Arena as BaseArena
from GameFolder.effects.GAME_effects import (
    ConeEffect,
    RadialEffect,
    LineEffect,
    WaveProjectileEffect,
    ObstacleEffect,
    ZoneIndicator,
)
from GameFolder.world.GAME_world_objects import WorldObstacle, GrassField
from GameFolder.pickups.GAME_pickups import AbilityPickup, PRIMARY_ABILITY_NAMES, PASSIVE_ABILITY_NAMES
from GameFolder.ui.GAME_ui import GameUI


class Arena(BaseArena):
    """MS2 arena implementation with obstacles, grass, abilities, and effects."""

    def __init__(self, width: int = 1400, height: int = 900, headless: bool = False):
        super().__init__(width, height, headless=headless)
        self.platforms = []
        self.weapon_pickups = []
        self.projectiles = []

        self.grass_fields = []
        self.obstacles = []
        self.effects = []

        self.zone_indicator = ZoneIndicator(self.safe_zone.center[:], self.safe_zone.radius)

        self.effect_hit_times = {}
        self.cow_hit_times = {}

        self.ability_spawn_timer = 0.0
        self.ability_spawn_interval = 6.0
        self.max_primary_pickups = 4
        self.max_passive_pickups = 4

        self._spawn_world()
        self._spawn_initial_pickups()

        if not self.headless:
            self.ui = GameUI(self.screen, self.width, self.height)
        else:
            self.ui = None

    def _spawn_world(self):
        random.seed(42)
        for _ in range(8):
            size = random.randint(50, 120)
            cx = random.randint(size, self.width - size)
            cy = random.randint(size, self.height - size)
            obstacle = WorldObstacle(cx, cy, size, "blocking", self.height)
            self.obstacles.append(obstacle)
            self.platforms.append(obstacle)

        for _ in range(6):
            size = random.randint(60, 140)
            cx = random.randint(size, self.width - size)
            cy = random.randint(size, self.height - size)
            obstacle = WorldObstacle(cx, cy, size, "slowing", self.height)
            self.obstacles.append(obstacle)
            self.platforms.append(obstacle)

        for _ in range(10):
            radius = random.randint(20, 60)
            cx = random.randint(radius, self.width - radius)
            cy = random.randint(radius, self.height - radius)
            grass = GrassField(cx, cy, radius, max_food=10, arena_height=self.height)
            self.grass_fields.append(grass)
            self.platforms.append(grass)

    def _spawn_initial_pickups(self):
        for _ in range(3):
            self._spawn_ability_pickup("primary")
        for _ in range(3):
            self._spawn_ability_pickup("passive")

    def _spawn_ability_pickup(self, ability_type: str):
        if ability_type == "primary":
            ability_name = random.choice(PRIMARY_ABILITY_NAMES)
        else:
            ability_name = random.choice(PASSIVE_ABILITY_NAMES)

        for _ in range(12):
            x = random.uniform(60, self.width - 60)
            y = random.uniform(60, self.height - 60)
            blocked = False
            for obstacle in self.obstacles:
                if abs(x - obstacle.world_center[0]) < obstacle.size / 2 + 40 and abs(y - obstacle.world_center[1]) < obstacle.size / 2 + 40:
                    blocked = True
                    break
            if blocked:
                continue
            pickup = AbilityPickup(ability_name, ability_type, [x, y])
            self.weapon_pickups.append(pickup)
            return

    def update(self, delta_time: float):
        for grass in self.grass_fields:
            grass.regrow(delta_time)

        super().update(delta_time)

        self.zone_indicator.update_from_safe_zone(self.safe_zone.center[:], self.safe_zone.radius)
        self.projectiles = self.effects + [self.zone_indicator]

        self._manage_pickups(delta_time)

    def _manage_pickups(self, delta_time: float):
        self.ability_spawn_timer += delta_time
        if self.ability_spawn_timer < self.ability_spawn_interval:
            return
        self.ability_spawn_timer = 0.0

        primary_count = len([p for p in self.weapon_pickups if p.ability_type == "primary"])
        passive_count = len([p for p in self.weapon_pickups if p.ability_type == "passive"])

        if primary_count < self.max_primary_pickups:
            self._spawn_ability_pickup("primary")
        if passive_count < self.max_passive_pickups:
            self._spawn_ability_pickup("passive")

    def handle_collisions(self):
        for cow in self.characters:
            if not cow.is_alive:
                continue
            cow.is_slowed = False

            self._resolve_obstacle_collisions(cow)
            self._resolve_poops(cow)
            self._apply_effects(cow)

        self._resolve_cow_collisions()

        for pickup in self.weapon_pickups[:]:
            if not pickup.is_active:
                continue
            pickup_rect = pickup.get_pickup_rect(self.height)
            for cow in self.characters:
                if not cow.is_alive:
                    continue
                cow_rect = cow.get_rect(self.height)
                if cow_rect.colliderect(pickup_rect):
                    if pickup.ability_type == "primary":
                        if cow.primary_ability_name is None:
                            cow.set_primary_ability(pickup.ability_name)
                        else:
                            continue
                    else:
                        if cow.passive_ability_name is None:
                            cow.set_passive_ability(pickup.ability_name)
                        else:
                            continue
                    pickup.pickup()
                    if pickup in self.weapon_pickups:
                        self.weapon_pickups.remove(pickup)
                    break

    def _resolve_obstacle_collisions(self, cow):
        cow_radius = cow.size / 2
        for obstacle in self.obstacles:
            dx = cow.location[0] - obstacle.world_center[0]
            dy = cow.location[1] - obstacle.world_center[1]
            overlap_x = cow_radius + obstacle.size / 2 - abs(dx)
            overlap_y = cow_radius + obstacle.size / 2 - abs(dy)

            if overlap_x > 0 and overlap_y > 0:
                if obstacle.obstacle_type == "slowing":
                    cow.is_slowed = True
                    continue
                if overlap_x < overlap_y:
                    cow.location[0] += overlap_x if dx > 0 else -overlap_x
                else:
                    cow.location[1] += overlap_y if dy > 0 else -overlap_y

    def _resolve_poops(self, cow):
        for effect in self.effects[:]:
            if not isinstance(effect, ObstacleEffect):
                continue
            if effect.owner_id == cow.id:
                continue
            cow_rect = cow.get_rect(self.height)
            poop_rect = effect.get_rect(self.height)
            if cow_rect.colliderect(poop_rect):
                if effect.mine:
                    cow.take_damage(effect.size / 3)
                    if effect in self.effects:
                        self.effects.remove(effect)
                elif effect.wall:
                    self._push_out_of_rect(cow, poop_rect)

    def _apply_effects(self, cow):
        for effect in self.effects:
            if isinstance(effect, ObstacleEffect):
                continue
            if hasattr(effect, "owner_id") and effect.owner_id == cow.id:
                continue

            hit = False
            if isinstance(effect, ConeEffect):
                hit = self._point_in_triangle(cow.location, effect.get_triangle_points())
                if hit:
                    cow.is_slowed = True
            elif isinstance(effect, RadialEffect):
                hit = self._point_in_circle(cow.location, effect.location, effect.radius)
            elif isinstance(effect, LineEffect):
                hit = self._point_in_arc(cow.location, effect.location, effect.angle, effect.length, effect.width)
            elif isinstance(effect, WaveProjectileEffect):
                cow_rect = cow.get_rect(self.height)
                hit = cow_rect.colliderect(effect.get_rect(self.height))

            if not hit:
                continue

            key = (effect.network_id, cow.id)
            last_hit = self.effect_hit_times.get(key, 0.0)
            cooldown = getattr(effect, "damage_cooldown", 0.4)
            if self.current_time - last_hit < cooldown:
                continue

            damage = getattr(effect, "damage", 0.0)
            if damage > 0:
                cow.take_damage(damage)
            self.effect_hit_times[key] = self.current_time

            knockback = getattr(effect, "knockback_distance", 0.0)
            if knockback > 0:
                self._apply_knockback(cow, effect.location, knockback)

    def _resolve_cow_collisions(self):
        for i in range(len(self.characters)):
            for j in range(i + 1, len(self.characters)):
                cow_a = self.characters[i]
                cow_b = self.characters[j]
                if not cow_a.is_alive or not cow_b.is_alive:
                    continue
                rect_a = cow_a.get_rect(self.height)
                rect_b = cow_b.get_rect(self.height)
                if not rect_a.colliderect(rect_b):
                    continue

                pair_key = tuple(sorted([cow_a.id, cow_b.id]))
                last_hit = self.cow_hit_times.get(pair_key, 0.0)
                if self.current_time - last_hit < 0.6:
                    continue

                if cow_a.is_attacking and not cow_b.is_attacking:
                    cow_b.take_damage(cow_a.primary_damage * cow_a.damage_multiplier)
                    self.cow_hit_times[pair_key] = self.current_time
                elif cow_b.is_attacking and not cow_a.is_attacking:
                    cow_a.take_damage(cow_b.primary_damage * cow_b.damage_multiplier)
                    self.cow_hit_times[pair_key] = self.current_time

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
        overlap_x = cow_rect.width / 2 + obstacle_rect.width / 2 - abs(cow_rect.centerx - obstacle_rect.centerx)
        overlap_y = cow_rect.height / 2 + obstacle_rect.height / 2 - abs(cow_rect.centery - obstacle_rect.centery)
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
    def _point_in_circle(point, center, radius) -> bool:
        dx = point[0] - center[0]
        dy = point[1] - center[1]
        return dx * dx + dy * dy <= radius * radius

    @staticmethod
    def _point_in_triangle(point, triangle_points) -> bool:
        (x1, y1), (x2, y2), (x3, y3) = triangle_points
        px, py = point
        denom = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if denom == 0:
            return False
        a = ((y2 - y3) * (px - x3) + (x3 - x2) * (py - y3)) / denom
        b = ((y3 - y1) * (px - x3) + (x1 - x3) * (py - y3)) / denom
        c = 1 - a - b
        return 0 <= a <= 1 and 0 <= b <= 1 and 0 <= c <= 1

    @staticmethod
    def _point_in_arc(point, center, angle, length, width) -> bool:
        dx = point[0] - center[0]
        dy = point[1] - center[1]
        dist = math.hypot(dx, dy)
        if dist > length or dist == 0:
            return False
        point_angle = math.atan2(dy, dx)
        half_angle = math.atan2(width / 2, max(1.0, dist))
        diff = (point_angle - angle + math.pi) % (2 * math.pi) - math.pi
        return abs(diff) <= half_angle

    def render(self):
        if self.headless:
            return
        camera = getattr(self, "camera", None)
        self.screen.fill((20, 90, 20))
        for platform in self.platforms:
            platform.draw(self.screen, self.height, camera=camera)
        for effect in self.effects:
            effect.draw(self.screen, self.height, camera=camera)
        self.zone_indicator.draw(self.screen, self.height, camera=camera)
        for pickup in self.weapon_pickups:
            pickup.draw(self.screen, self.height, camera=camera)
        for cow in self.characters:
            cow.draw(self.screen, self.height, camera=camera)
        if self.ui:
            self.ui.draw(self.characters, self.game_over, self.winner, self.respawn_timer)
        pygame.display.flip()
