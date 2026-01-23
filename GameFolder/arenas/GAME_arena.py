import math
import random
import pygame
from BASE_components.BASE_arena import Arena as BaseArena, WORLD_WIDTH, WORLD_HEIGHT
from BASE_components.BASE_asset_handler import AssetHandler
from GameFolder.effects.coneeffect import ConeEffect
from GameFolder.effects.radialeffect import RadialEffect
from GameFolder.effects.lineeffect import LineEffect
from GameFolder.effects.waveprojectileeffect import WaveProjectileEffect
from GameFolder.effects.obstacleeffect import ObstacleEffect
from GameFolder.effects.zoneindicator import ZoneIndicator
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

        self.num_blocking_obstacles = 100
        self.num_slowing_obstacles = 50
        self.num_grass_fields = 30

        self._spawn_world()
        self._spawn_initial_pickups()

        # Load random background image from category if available
        self.background_tile = None
        self.background_tile_size = None
        self.background_variant = None
        if not self.headless:
            self.ui = GameUI(self.screen, self.width, self.height)
            # Try to load random background from background category (at original size for tiling)
            bg_surface, loaded, variant = AssetHandler.get_image_from_category(
                "background",
                variant=None,  # Pick random variant
                frame=0,
                size=None,  # Load at original size for tiling
            )
            if loaded and bg_surface is not None:
                # Store the tile image and its size for infinite tiling
                self.background_tile = bg_surface
                self.background_tile_size = bg_surface.get_size()
                self.background_variant = variant
        else:
            self.ui = None

    def _spawn_world(self):
        for _ in range(self.num_grass_fields):
            radius = random.randint(20, 60)
            cx = random.randint(radius, self.width - radius)
            cy = random.randint(radius, self.height - radius)
            grass = GrassField(cx, cy, radius, max_food=10, arena_height=self.height)
            self.grass_fields.append(grass)
            self.platforms.append(grass)
        
        for _ in range(self.num_slowing_obstacles):
            size = random.randint(60, 140)
            cx = random.randint(size, self.width - size)
            cy = random.randint(size, self.height - size)
            obstacle = WorldObstacle(cx, cy, size, "slowing", self.height)
            self.obstacles.append(obstacle)
            self.platforms.append(obstacle)
        
        for _ in range(self.num_blocking_obstacles):
            size = random.randint(50, 120)
            cx = random.randint(size, self.width - size)
            cy = random.randint(size, self.height - size)
            obstacle = WorldObstacle(cx, cy, size, "blocking", self.height)
            self.obstacles.append(obstacle)
            self.platforms.append(obstacle)


    def _spawn_initial_pickups(self):
        for _ in range(30):
            self._spawn_ability_pickup("primary")
        for _ in range(30):
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
                            cow.set_primary_ability(pickup.ability_name, from_pickup=True)
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
            cow_radius = cow.size / 2
            if isinstance(effect, ConeEffect):
                hit = self._circle_intersects_triangle(cow.location, cow_radius, effect.get_triangle_points())
                if hit:
                    cow.is_slowed = True
            elif isinstance(effect, RadialEffect):
                hit = self._circle_intersects_circle(cow.location, cow_radius, effect.location, effect.radius)
            elif isinstance(effect, LineEffect):
                hit = self._circle_intersects_line(cow.location, cow_radius, effect.location, effect.angle, effect.length, effect.width)
            elif isinstance(effect, WaveProjectileEffect):
                cow_rect = cow.get_rect(self.height)
                hit = cow_rect.colliderect(effect.get_rect(self.height))

            if not hit:
                continue

            key = (effect.network_id, cow.id)
            last_hit = self.effect_hit_times.get(key, 0.0)
            cooldown = getattr(effect, "damage_cooldown", 0.4)
            # Allow first hit (last_hit == 0.0 means never hit before)
            # For subsequent hits, check cooldown
            if last_hit > 0.0 and self.current_time - last_hit < cooldown:
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
    def _circle_intersects_circle(circle1_center, circle1_radius, circle2_center, circle2_radius) -> bool:
        """Check if two circles intersect."""
        dx = circle1_center[0] - circle2_center[0]
        dy = circle1_center[1] - circle2_center[1]
        dist_sq = dx * dx + dy * dy
        radius_sum = circle1_radius + circle2_radius
        return dist_sq <= radius_sum * radius_sum

    @staticmethod
    def _circle_intersects_triangle(circle_center, circle_radius, triangle_points) -> bool:
        """Check if a circle intersects with a triangle."""
        (x1, y1), (x2, y2), (x3, y3) = triangle_points
        cx, cy = circle_center
        
        # Check if circle center is inside triangle
        denom = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if denom != 0:
            a = ((y2 - y3) * (cx - x3) + (x3 - x2) * (cy - y3)) / denom
            b = ((y3 - y1) * (cx - x3) + (x1 - x3) * (cy - y3)) / denom
            c = 1 - a - b
            if 0 <= a <= 1 and 0 <= b <= 1 and 0 <= c <= 1:
                return True
        
        # Check if circle intersects any triangle edge
        edges = [
            ((x1, y1), (x2, y2)),
            ((x2, y2), (x3, y3)),
            ((x3, y3), (x1, y1))
        ]
        for (p1x, p1y), (p2x, p2y) in edges:
            # Distance from circle center to line segment
            dx = p2x - p1x
            dy = p2y - p1y
            line_len_sq = dx * dx + dy * dy
            if line_len_sq == 0:
                # Edge is a point
                dist = math.hypot(cx - p1x, cy - p1y)
                if dist <= circle_radius:
                    return True
            else:
                # Project circle center onto line segment
                t = max(0, min(1, ((cx - p1x) * dx + (cy - p1y) * dy) / line_len_sq))
                proj_x = p1x + t * dx
                proj_y = p1y + t * dy
                dist = math.hypot(cx - proj_x, cy - proj_y)
                if dist <= circle_radius:
                    return True
        
        return False

    @staticmethod
    def _circle_intersects_line(circle_center, circle_radius, line_start, angle, length, width) -> bool:
        """Check if a circle intersects with a line segment (arc)."""
        cx, cy = circle_center
        
        # Calculate line end point
        line_end = (
            line_start[0] + length * math.cos(angle),
            line_start[1] + length * math.sin(angle)
        )
        
        # Distance from circle center to line segment
        dx = line_end[0] - line_start[0]
        dy = line_end[1] - line_start[1]
        line_len_sq = dx * dx + dy * dy
        
        if line_len_sq == 0:
            # Line is a point
            dist = math.hypot(cx - line_start[0], cy - line_start[1])
            return dist <= circle_radius + width / 2
        
        # Project circle center onto line segment
        t = max(0, min(1, ((cx - line_start[0]) * dx + (cy - line_start[1]) * dy) / line_len_sq))
        proj_x = line_start[0] + t * dx
        proj_y = line_start[1] + t * dy
        
        # Distance from circle center to projected point
        dist_to_line = math.hypot(cx - proj_x, cy - proj_y)
        
        # Check if within width/2 + circle_radius
        return dist_to_line <= (width / 2) + circle_radius

    def render(self):
        if self.headless:
            return
        # additional safety check: ensure screen exists
        if self.screen is None:
            return
        camera = getattr(self, "camera", None)
        
        # Draw background image if available, otherwise use green color
        if self.background_tile is not None and camera is not None:
            # Get camera viewport in world coordinates
            left, bottom, right, top = camera.get_viewport()
            
            bg_width, bg_height = self.background_tile_size
            
            # Calculate which tiles we need to draw (infinite tiling)
            # Start from the leftmost/bottommost tile that intersects the viewport
            start_tile_x = int(left // bg_width)
            start_tile_y = int(bottom // bg_height)
            end_tile_x = int((right + bg_width - 1) // bg_width)
            end_tile_y = int((top + bg_height - 1) // bg_height)
            
            # Draw all tiles that intersect the viewport
            for tile_y in range(start_tile_y, end_tile_y + 1):
                for tile_x in range(start_tile_x, end_tile_x + 1):
                    # Calculate world position of this tile
                    tile_world_x = tile_x * bg_width
                    tile_world_y = tile_y * bg_height
                    
                    # Convert to screen coordinates
                    screen_x, screen_y = camera.world_to_screen_point(tile_world_x, tile_world_y + bg_height)
                    screen_x = int(screen_x)
                    screen_y = int(screen_y)
                    
                    # Calculate how much of this tile is visible in world coordinates
                    tile_left = max(left, tile_world_x)
                    tile_bottom = max(bottom, tile_world_y)
                    tile_right = min(right, tile_world_x + bg_width)
                    tile_top = min(top, tile_world_y + bg_height)
                    
                    # Calculate source rect within the tile (tile surface uses y-down)
                    # Tile surface: y=0 at top, y=bg_height at bottom
                    # World: tile_world_y is bottom, tile_world_y + bg_height is top
                    src_x = int(tile_left - tile_world_x)
                    # Convert from world y-up to tile surface y-down
                    # Visible area in world: from tile_bottom (low y) to tile_top (high y)
                    # In tile surface: top of visible = bg_height - (tile_top - tile_world_y)
                    #                  bottom of visible = bg_height - (tile_bottom - tile_world_y)
                    src_y = int(bg_height - (tile_top - tile_world_y))
                    src_width = int(tile_right - tile_left)
                    src_height = int(tile_top - tile_bottom)
                    
                    # Calculate destination on screen (convert world coords to screen coords)
                    # world_to_screen_point converts: screen_y = top - world_y
                    # So for tile_top (high world y), we get low screen y (top of screen)
                    # We want to draw at the top of the visible area on screen
                    dest_x, dest_y = camera.world_to_screen_point(tile_left, tile_top)
                    dest_x = int(dest_x)
                    dest_y = int(dest_y)
                    
                    # Blit the visible portion of this tile
                    if src_width > 0 and src_height > 0:
                        src_rect = pygame.Rect(src_x, src_y, src_width, src_height)
                        self.screen.blit(self.background_tile, (dest_x, dest_y), area=src_rect)
        elif self.background_tile is not None:
            # No camera, just tile the background (shouldn't happen in normal gameplay)
            bg_width, bg_height = self.background_tile_size
            for y in range(0, self.height, bg_height):
                for x in range(0, self.width, bg_width):
                    self.screen.blit(self.background_tile, (x, y))
        else:
            self.screen.fill((20, 90, 20))  # Grass green background fallback
        
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
        # safely handle display flip - catch OpenGL context errors
        try:
            pygame.display.flip()
        except pygame.error as e:
            print(f"Error flipping display: {e}")
            # silently ignore OpenGL context errors in test/headless environments
            if "GL context" not in str(e) and "BadAccess" not in str(e):
                raise  # re-raise if it's a different error
