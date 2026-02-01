import inspect
import math
import random
import pygame
from BASE_components.BASE_arena import Arena as BaseArena, WORLD_WIDTH, WORLD_HEIGHT
from BASE_components.BASE_asset_handler import AssetHandler
from BASE_components.BASE_spatial import SpatialGrid
from BASE_components.BASE_character import BaseCharacter
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
        self.max_primary_pickups = 16
        self.max_passive_pickups = 16

        self.num_blocking_obstacles = 100
        self.num_slowing_obstacles = 50
        self.num_grass_fields = 30

        # Initialize spatial grid for server-side collision optimization
        # Must be initialized BEFORE spawning pickups, as they check for obstacles
        self.spatial_grid = SpatialGrid(cell_size=250)

        self._spawn_world()
        
        # Update spatial grid with world obstacles so pickups can avoid them
        self._update_spatial_grid()
        
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
        max_margin = max(1, int(min(self.width, self.height) / 2) - 1)

        def _clamped_rand(min_value: int, max_value: int):
            capped_max = min(max_value, max_margin)
            if capped_max < 1:
                return None
            capped_min = min(min_value, capped_max)
            return random.randint(capped_min, capped_max)

        for _ in range(self.num_grass_fields):
            radius = _clamped_rand(20, 60)
            if radius is None:
                break
            cx = random.randint(radius, self.width - radius)
            cy = random.randint(radius, self.height - radius)
            grass = GrassField(cx, cy, radius, max_food=10, arena_height=self.height)
            self.grass_fields.append(grass)
            self.platforms.append(grass)
        
        for _ in range(self.num_slowing_obstacles):
            size = _clamped_rand(60, 140)
            if size is None:
                break
            cx = random.randint(size, self.width - size)
            cy = random.randint(size, self.height - size)
            obstacle = WorldObstacle(cx, cy, size, "slowing", self.height)
            self.obstacles.append(obstacle)
            self.platforms.append(obstacle)
        
        for _ in range(self.num_blocking_obstacles):
            # Weighted random selection favoring big obstacles
            # Small (50-70): 10% chance, Medium (71-95): 30% chance, Big (96-200): 60% chance
            rand = random.random()
            if rand < 0.1:  # 10% chance for small
                size = _clamped_rand(50, 70)
            elif rand < 0.4:  # 30% chance for medium
                size = _clamped_rand(71, 95)
            else:  # 60% chance for big
                size = _clamped_rand(96, 200)
            if size is None:
                break
            
            cx = random.randint(size, self.width - size)
            cy = random.randint(size, self.height - size)
            obstacle = WorldObstacle(cx, cy, size, "blocking", self.height)
            self.obstacles.append(obstacle)
            self.platforms.append(obstacle)
        
        # Sort obstacles by Y position for correct z-ordering (top to bottom on screen)
        # screen_y = top - world_y, so: higher world_y → top of screen, lower world_y → bottom of screen
        # We want: top of screen drawn first (behind), bottom of screen drawn last (on top)
        # So sort descending: higher world_y first, lower world_y last
        self.obstacles.sort(key=lambda o: o.world_center[1], reverse=True)
        # Sort grass fields by Y position for correct z-ordering
        self.grass_fields.sort(key=lambda g: g.world_center[1], reverse=True)


    def _spawn_initial_pickups(self):
        for _ in range(self.max_primary_pickups//4):
            self._spawn_ability_pickup("primary")
        for _ in range(self.max_passive_pickups//4):
            self._spawn_ability_pickup("passive")

    def _spawn_ability_pickup(self, ability_type: str):
        if ability_type == "primary":
            ability_name = random.choice(PRIMARY_ABILITY_NAMES)
        else:
            ability_name = random.choice(PASSIVE_ABILITY_NAMES)

        for _ in range(12):
            x = random.uniform(60, self.width - 60)
            y = random.uniform(60, self.height - 60)
            
            # Optimized check using spatial grid
            nearby_obstacles = self.spatial_grid.get_nearby(x, y, 150)
            blocked = False
            for obstacle in nearby_obstacles:
                if not isinstance(obstacle, WorldObstacle):
                    continue
                dx = x - obstacle.world_center[0]
                dy = y - obstacle.world_center[1]
                distance_sq = dx * dx + dy * dy
                if distance_sq < (obstacle.size / 2 + 40) ** 2:
                    blocked = True
                    break
            if blocked:
                continue
            pickup = AbilityPickup(ability_name, ability_type, [x, y])
            self.weapon_pickups.append(pickup)
            return

    def _update_spatial_grid(self):
        """Rebuild spatial grid with all interactive objects."""
        self.spatial_grid.clear()
        
        # Add everything that can be interacted with
        for obstacle in self.obstacles:
            self.spatial_grid.add(obstacle)
        for grass in self.grass_fields:
            self.spatial_grid.add(grass)
        for pickup in self.weapon_pickups:
            if pickup.is_active:
                self.spatial_grid.add(pickup)
        for effect in self.effects:
            self.spatial_grid.add(effect)
        for cow in self.characters:
            if cow.is_alive:
                self.spatial_grid.add(cow)

    def update(self, delta_time: float):
        for grass in self.grass_fields:
            grass.regrow(delta_time)

        super().update(delta_time)
        
        # Update spatial grid every frame since obstacles might move (or be destroyed)
        # Note: If obstacles are static, we could do this less often or only when they move.
        # But for dynamic environments, per-frame update is safer.
        self._update_spatial_grid()

        self.zone_indicator.update_from_safe_zone(self.safe_zone.center[:], self.safe_zone.radius)
        self.projectiles = self.effects + [self.zone_indicator]

        self._manage_pickups(delta_time)

    def _effect_accepts_arena(self, effect) -> bool:
        cached = getattr(effect, "_accepts_arena_update", None)
        if cached is not None:
            return cached
        try:
            sig = inspect.signature(effect.update)
        except (TypeError, ValueError):
            cached = False
        else:
            params = list(sig.parameters.values())
            has_var = any(
                p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD) for p in params
            )
            cached = has_var or len(params) >= 2
        effect._accepts_arena_update = cached
        return cached

    def _update_effects(self, delta_time: float):
        active = []
        for effect in self.effects:
            expired = False
            if hasattr(effect, "update"):
                if self._effect_accepts_arena(effect):
                    expired = effect.update(delta_time, self)
                else:
                    expired = effect.update(delta_time)
            if not expired:
                active.append(effect)
        self.effects = active

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
        """Main collision and interaction pass using spatial grid."""
        # Rebuild grid to catch any movement from this frame
        self._update_spatial_grid()

        for cow in self.characters:
            if not cow.is_alive:
                continue
            cow.is_slowed = False
            
            cow_radius = cow.size / 2
            # Get nearby objects for this specific cow (generous radius)
            nearby = self.spatial_grid.get_nearby(cow.location[0], cow.location[1], cow_radius + 150)

            self._resolve_nearby_collisions(cow, nearby)
            self._resolve_nearby_pickups(cow, nearby)

        self._resolve_nearby_cow_collisions()

    def _resolve_nearby_collisions(self, cow, nearby):
        """Resolve collisions with obstacles, poops, and effects using a pre-filtered list."""
        cow_radius = cow.size / 2
        
        for obj in nearby:
            # 1. Obstacles (Explicitly check type to avoid GrassField collision)
            if isinstance(obj, WorldObstacle):
                obstacle_radius = obj.size / 2
                dx = cow.location[0] - obj.world_center[0]
                dy = cow.location[1] - obj.world_center[1]
                distance_sq = dx * dx + dy * dy
                radius_sum = cow_radius + obstacle_radius
                
                if distance_sq < radius_sum * radius_sum:
                    if obj.obstacle_type == "slowing":
                        cow.is_slowed = True
                    else:
                        distance = math.sqrt(distance_sq)
                        if distance == 0:
                            angle = random.uniform(0, 2 * math.pi)
                            dx, dy = math.cos(angle), math.sin(angle)
                            distance = 1.0
                        else:
                            dx /= distance
                            dy /= distance
                        overlap = radius_sum - distance
                        cow.location[0] += dx * overlap
                        cow.location[1] += dy * overlap

            # 2. Poops (ObstacleEffect)
            elif isinstance(obj, ObstacleEffect):
                if obj.owner_id == cow.id:
                    continue
                cow_rect = cow.get_rect(self.height)
                poop_rect = obj.get_rect(self.height)
                if cow_rect.colliderect(poop_rect):
                    if obj.mine:
                        cow.take_damage(obj.size / 3)
                        if obj in self.effects:
                            self.effects.remove(obj)
                    elif obj.wall:
                        self._push_out_of_rect(cow, poop_rect)

            # 3. Other Effects (including ZoneIndicator)
            elif isinstance(obj, (ConeEffect, RadialEffect, LineEffect, WaveProjectileEffect, ZoneIndicator)):
                # Ensure weapon owner filtering is robust
                if hasattr(obj, "owner_id") and obj.owner_id == cow.id:
                    continue

                hit = False
                if isinstance(obj, ZoneIndicator):
                    # Damage logic is handled in _apply_safe_zone_damage, but we could add it here
                    continue

                if isinstance(obj, ConeEffect):
                    hit = self._circle_intersects_triangle(cow.location, cow_radius, obj.get_triangle_points())
                    if hit: cow.is_slowed = True
                elif isinstance(obj, RadialEffect):
                    hit = self._circle_intersects_circle(cow.location, cow_radius, obj.location, obj.radius)
                elif isinstance(obj, LineEffect):
                    hit = self._circle_intersects_line(cow.location, cow_radius, obj.location, obj.angle, obj.length, obj.width)
                elif isinstance(obj, WaveProjectileEffect):
                    hit = cow.get_rect(self.height).colliderect(obj.get_rect(self.height))

                if hit:
                    key = (obj.network_id, cow.id)
                    last_hit = self.effect_hit_times.get(key, 0.0)
                    cooldown = getattr(obj, "damage_cooldown", 0.4)
                    if last_hit == 0.0 or self.current_time - last_hit >= cooldown:
                        damage = getattr(obj, "damage", 0.0)
                        if damage > 0: cow.take_damage(damage)
                        self.effect_hit_times[key] = self.current_time
                        knockback = getattr(obj, "knockback_distance", 0.0)
                        if knockback > 0: self._apply_knockback(cow, obj.location, knockback)

    def _resolve_nearby_pickups(self, cow, nearby):
        """Check for pickups using the nearby list."""
        cow_rect = cow.get_rect(self.height)
        for obj in nearby:
            if isinstance(obj, AbilityPickup) and obj.is_active:
                pickup_rect = obj.get_pickup_rect(self.height)
                if cow_rect.colliderect(pickup_rect):
                    if obj.ability_type == "primary":
                        if cow.primary_ability_name is None:
                            cow.set_primary_ability(obj.ability_name, from_pickup=True)
                        else: continue
                    else:
                        if cow.passive_ability_name is None:
                            cow.set_passive_ability(obj.ability_name)
                        else: continue
                    obj.pickup()
                    if obj in self.weapon_pickups:
                        self.weapon_pickups.remove(obj)
                    break

    def _resolve_nearby_cow_collisions(self):
        """Optimized cow-to-cow collision checking."""
        for cow_a in self.characters:
            if not cow_a.is_alive: continue
            
            # Only check cows near cow_a
            nearby = self.spatial_grid.get_nearby(cow_a.location[0], cow_a.location[1], cow_a.size * 2)
            for obj in nearby:
                if obj == cow_a or not isinstance(obj, BaseCharacter) or not obj.is_alive:
                    continue
                
                cow_b = obj
                # Ensure we only check each pair once
                if id(cow_a) >= id(cow_b):
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

    # Placeholder for old methods
    def _resolve_obstacle_collisions(self, cow): pass
    def _resolve_poops(self, cow): pass
    def _apply_effects(self, cow): pass
    def _resolve_cow_collisions(self): pass

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
        
        # Draw in specific order: grass, slowing obstacles, cows, blocking obstacles
        # 1. Draw grass fields (sorted by Y position)
        for grass in self.grass_fields:
            grass.draw(self.screen, self.height, camera=camera)
        
        # 2. Draw slowing obstacles (sorted top to bottom: top of screen first, bottom last)
        slowing_obstacles = [o for o in self.obstacles if o.obstacle_type == "slowing"]
        slowing_obstacles.sort(key=lambda o: o.world_center[1], reverse=True)  # Higher Y (top) first
        for obstacle in slowing_obstacles:
            obstacle.draw(self.screen, self.height, camera=camera)
        
        # 3. Draw effects and zone indicator
        for effect in self.effects:
            effect.draw(self.screen, self.height, camera=camera)
        self.zone_indicator.draw(self.screen, self.height, camera=camera)
        
        # 4. Draw pickups
        for pickup in self.weapon_pickups:
            pickup.draw(self.screen, self.height, camera=camera)
        
        # 5. Draw cows
        for cow in self.characters:
            cow.draw(self.screen, self.height, camera=camera)
        
        # 6. Draw blocking obstacles last (sorted top to bottom: top of screen first, bottom last)
        blocking_obstacles = [o for o in self.obstacles if o.obstacle_type == "blocking"]
        blocking_obstacles.sort(key=lambda o: o.world_center[1], reverse=True)  # Higher Y (top) first
        for obstacle in blocking_obstacles:
            obstacle.draw(self.screen, self.height, camera=camera)
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
