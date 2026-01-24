import math
import random
import pygame
from BASE_components.BASE_character import BaseCharacter
from BASE_components.BASE_asset_handler import AssetHandler
from GameFolder.abilities.ability_loader import get_primary_abilities, get_passive_abilities
from GameFolder.effects.obstacleeffect import ObstacleEffect


class Character(BaseCharacter):
    """MS2 cow implementation built on the low-level BaseCharacter."""

    POOP_OBSTACLE_SIZE_MULTIPLIER = 3.0

    def __init__(self, name, description, image, location, width=30, height=30):
        super().__init__(name, description, image, location, width, height)
        self.base_size = float(width)
        self.size = float(width)
        self.width = self.size
        self.height = self.size

        # Handle skin/variant selection
        if image:
            # If it's an old format (contains .png), use old system for backward compatibility
            if ".png" in str(image):
                self.skin_name = image
                self.cow_variant = None  # Use old system
            else:
                # Treat as variant name
                self.skin_name = None
                self.cow_variant = image
        else:
            # Pick random variant from cows category and store it
            self.skin_name = None
            self.cow_variant = AssetHandler.get_random_variant("cows")
            # If no variants found, will be None and will be set on first draw
        
        # Pick random variant for dead cow and store it
        self.dead_cow_variant = AssetHandler.get_random_variant("deadCows")
        # If no variants found, will be None and will be set on first draw
        # Keep old format for backward compatibility check
        self.dead_skin_name = "cadavere.png"  # Fallback for old system

        self.speed = 3.0
        self.base_max_health = 100.0
        self.max_health = self._compute_max_health_for_size(self.size)
        self.health = self.max_health

        self.damage_multiplier = 1.0
        self.primary_damage = 0.0
        
        self.primary_delay = 0.6
        self.primary_knockback = 0.0
        self.primary_use_cooldown = 0.2
        self.last_primary_use = 0.0

        self.primary_ability_name = None
        self.primary_ability = None
        self.primary_description = ""
        self.available_primary_abilities = 0
        self.max_primary_abilities = 1

        self.passive_ability_name = None
        self.passive_description = ""

        self.probability_of_gun = 0.1
        self.time_to_eat = 0.6
        self.eat_cooldown = 0.0
        self.eat_increase = 1.0
        self.is_eating = False

        self.poop_cooldown = 0.8
        self.poop_timer = 0.0
        self.poop_percentage = 10
        self.mine_poop = False
        self.mine_wall = False

        self.dashes_left = 3
        self.max_dashes = 3
        self.dash_recharge_timer = 0.0
        self.time_to_recharge_dash = 1.0
        self.dash_multiplier = 5.0
        self.is_slowed = False
        self._dash_held = False
        self._swap_held = False

        self.is_attacking = False
        self.horn_charge_duration = 2.0
        self.horn_charge_end_time = 0.0
        self.attack_speed_multiplier = 1.9

        self.regeneration_rate = 0.0
        self.regenation = False
        self.can_get_angry = False
        self.angry = False

        self.color = (240, 240, 255)

        self.update_damage_multiplier()

    def __setstate__(self, state):
        super().__setstate__(state)
        if not hasattr(self, "size"):
            self.size = float(self.width)
        if not hasattr(self, "base_size"):
            self.base_size = float(self.width)
        
        if not hasattr(self, "dashes_left"):
            self.dashes_left = 3
        if not hasattr(self, "max_dashes"):
            self.max_dashes = 3
        if not hasattr(self, "dash_recharge_timer"):
            self.dash_recharge_timer = 0.0
        if not hasattr(self, "time_to_recharge_dash"):
            self.time_to_recharge_dash = 1.0
        if not hasattr(self, "primary_use_cooldown"):
            self.primary_use_cooldown = 0.2
        if not hasattr(self, "last_primary_use"):
            self.last_primary_use = 0.0
        if not hasattr(self, "is_slowed"):
            self.is_slowed = False
        if not hasattr(self, "is_eating"):
            self.is_eating = False
        if not hasattr(self, "primary_ability_name"):
            self.primary_ability_name = None
        if not hasattr(self, "primary_description"):
            self.primary_description = ""
        if not hasattr(self, "passive_ability_name"):
            self.passive_ability_name = None
        if not hasattr(self, "passive_description"):
            self.passive_description = ""
        if not hasattr(self, "available_primary_abilities"):
            self.available_primary_abilities = 0
        if not hasattr(self, "max_primary_abilities"):
            self.max_primary_abilities = 1
        if not hasattr(self, "mine_poop"):
            self.mine_poop = False
        if not hasattr(self, "mine_wall"):
            self.mine_wall = False
        if not hasattr(self, "can_get_angry"):
            self.can_get_angry = False
        if not hasattr(self, "angry"):
            self.angry = False
        if not hasattr(self, "primary_damage"):
            self.primary_damage = 0.0
        if not hasattr(self, "primary_delay"):
            self.primary_delay = 0.6
        if not hasattr(self, "_swap_held"):
            self._swap_held = False
        if not hasattr(self, "skin_name"):
            self.skin_name = random.choice(["mucca0.png", "mucca1.png", "mucca2.png", "mucca3.png"])
        if not hasattr(self, "dead_skin_name"):
            self.dead_skin_name = "cadavere.png"

    def _compute_max_health_for_size(self, size: float) -> float:
        size_delta = max(0.0, size - self.base_size)
        # Super-linear growth: big bodies get disproportionately tanky.
        return self.base_max_health + (size_delta ** 1.35) * 2.0

    @staticmethod
    def get_input_data(held_keys, mouse_buttons, mouse_pos):
        input_data = BaseCharacter.get_input_data(held_keys, mouse_buttons, mouse_pos)

        if pygame.K_SPACE in held_keys:
            input_data["eat"] = True
        if pygame.K_LSHIFT in held_keys or pygame.K_RSHIFT in held_keys:
            input_data["dash"] = True
        if pygame.K_p in held_keys:
            input_data["poop"] = True
        if pygame.K_q in held_keys:
            input_data["swap"] = True
        if mouse_buttons[0]:
            input_data["primary"] = mouse_pos
        return input_data

    def process_input(self, input_data: dict, arena):
        if not self.is_alive:
            return
        swap_pressed = input_data.get("swap", False)
        swap = swap_pressed and not self._swap_held
        self._swap_held = swap_pressed
        if swap:
            self.try_swap_ability(arena)
        if input_data.get("eat"):
            self.try_eat(arena)
        if input_data.get("poop"):
            self.try_poop(arena)
        if "primary" in input_data:
            self.use_primary_ability(arena, input_data.get("primary"))

        move_dir = input_data.get("movement", [0, 0])
        dash_pressed = input_data.get("dash", False)
        dash = dash_pressed and not self._dash_held
        self._dash_held = dash_pressed
        self.move(move_dir, arena, input_data.get("mouse_pos"), dash)

    def try_swap_ability(self, arena):
        """
        Swap the cow's current ability with the pickup you're standing on.

        - If the relevant slot is empty, behaves like a normal pickup (assign + remove pickup).
        - Otherwise, exchanges the cow's ability with the pickup's stored ability.
        """
        cow_rect = self.get_rect(arena.height)
        for pickup in getattr(arena, "weapon_pickups", [])[:]:
            if not getattr(pickup, "is_active", False):
                continue
            pickup_rect = pickup.get_pickup_rect(arena.height)
            if not cow_rect.colliderect(pickup_rect):
                continue

            if pickup.ability_type == "primary":
                if self.primary_ability_name is None:
                    self.set_primary_ability(pickup.ability_name, from_pickup=True)
                    pickup.pickup()
                    if pickup in arena.weapon_pickups:
                        arena.weapon_pickups.remove(pickup)
                else:
                    old = self.primary_ability_name
                    new = pickup.ability_name
                    self.set_primary_ability(new, from_pickup=True)
                    pickup.set_ability_name(old)
            else:
                if self.passive_ability_name is None:
                    self.set_passive_ability(pickup.ability_name)
                    pickup.pickup()
                    if pickup in arena.weapon_pickups:
                        arena.weapon_pickups.remove(pickup)
                else:
                    old = self.passive_ability_name
                    new = pickup.ability_name
                    self.set_passive_ability(new)
                    pickup.set_ability_name(old)
            return

    def update(self, delta_time: float, arena):
        super().update(delta_time, arena)
        if arena is None:
            return

        if not hasattr(self, "skin_name"):
            self.skin_name = random.choice(["mucca0.png", "mucca1.png", "mucca2.png", "mucca3.png"])
        if not hasattr(self, "dead_skin_name"):
            self.dead_skin_name = "cadavere.png"

        if self.is_attacking and arena.current_time >= self.horn_charge_end_time:
            self.is_attacking = False

        if self.eat_cooldown > 0:
            self.eat_cooldown = max(0.0, self.eat_cooldown - delta_time)
            self.is_eating = True
        else:
            self.is_eating = False

        if self.poop_timer > 0:
            self.poop_timer = max(0.0, self.poop_timer - delta_time)

        if self.dashes_left < self.max_dashes:
            self.dash_recharge_timer += delta_time
            if self.dash_recharge_timer >= self.time_to_recharge_dash:
                self.dashes_left += 1
                self.dash_recharge_timer = 0.0

        if self.regenation and self.health < self.max_health:
            self.health = min(self.max_health, self.health + self.regeneration_rate * delta_time)

        if self.can_get_angry:
            if self.health <= self.max_health * 0.25:
                if not self.angry:
                    self.damage_multiplier += self.damage_multiplier / 2
                    self.angry = True
            else:
                if self.angry:
                    self.angry = False
                    self.update_damage_multiplier()
        
    def move(self, direction, arena, mouse_pos=None, dash=False):
        if not self.is_alive:
            return
        if self.is_eating:
            return

        dx, dy = direction
        speed = self.speed
        if self.is_slowed:
            speed *= 0.6

        if dash and self.dashes_left > 0 and self.dash_recharge_timer <= 0.0:
            speed *= self.dash_multiplier
            self.dashes_left -= 1
            self.dash_recharge_timer = 0.0

        if self.is_attacking and mouse_pos is not None:
            target_x, target_y = mouse_pos
            vec_x = target_x - self.location[0]
            vec_y = target_y - self.location[1]
            dist = math.hypot(vec_x, vec_y)
            if dist > 0:
                dx = vec_x / dist
                dy = vec_y / dist
                speed *= self.attack_speed_multiplier

        if dx != 0 and dy != 0:
            speed /= math.sqrt(2)

        self._update_movement_state(dx, dy)

        self.location[0] += dx * speed
        self.location[1] += dy * speed

        margin = self.size / 2
        self.location[0] = max(margin, min(arena.width - margin, self.location[0]))
        self.location[1] = max(margin, min(arena.height - margin, self.location[1]))

    def try_eat(self, arena):
        if self.eat_cooldown > 0:
            return
        for field in arena.grass_fields:
            if field.can_eat(self.location[0], self.location[1], self.size / 2):
                if field.eat():
                    self.size += self.eat_increase
                    self.heal(0.5)

                    if random.random() < self.probability_of_gun:
                        if self.available_primary_abilities < self.max_primary_abilities:
                            self.available_primary_abilities += 1

                    self.changed_size()
                    self.eat_cooldown = self.time_to_eat
                    self.is_eating = True
                    return

    def try_poop(self, arena):
        if self.poop_timer > 0:
            return
        poop_size = max(4.0, self.size * (self.poop_percentage / 100.0))
        self.size = max(9.0, self.size - poop_size)
        self.changed_size()

        poop = ObstacleEffect(
            location=[self.location[0], self.location[1]],
            size=poop_size * self.POOP_OBSTACLE_SIZE_MULTIPLIER,
            owner_id=self.id,
            mine=self.mine_poop,
            wall=self.mine_wall,
        )
        arena.add_effect(poop)
        self.poop_timer = self.poop_cooldown

    def use_primary_ability(self, arena, mouse_pos):
        if not self.primary_ability or self.available_primary_abilities <= 0:
            return
        if arena.current_time - self.last_primary_use < self.primary_use_cooldown:
            return
        self.last_primary_use = arena.current_time
        self.available_primary_abilities -= 1
        self.primary_ability(self, arena, mouse_pos)

    def set_primary_ability(self, ability_name: str, from_pickup: bool = False):
        """
        Set the primary ability for this character.
        
        Args:
            ability_name: Name of the ability to set
            from_pickup: If True, weapon starts empty (0 ammo). If False (default),
                        weapon starts with full ammo. When swapping weapons, ammo is preserved.
        """
        if ability_name is None:
            self.primary_ability_name = None
            self.primary_ability = None
            self.primary_description = ""
            self.available_primary_abilities = 0
            return

        ability_def = None
        for ability in get_primary_abilities():
            if ability["name"] == ability_name:
                ability_def = ability
                break
        if ability_def is None:
            return
        
        # Store current ammo if swapping weapons (preserve ammo when switching from pickup)
        was_swapping = self.primary_ability_name is not None
        current_ammo = self.available_primary_abilities if was_swapping else 0
        
        self.primary_ability = ability_def["activate"]
        self.primary_ability_name = ability_def["name"]
        self.primary_description = ability_def["description"]
        self.max_primary_abilities = ability_def["max_charges"]
        
        # Set ammo based on context:
        # - Programmatic/test (from_pickup=False): Always full ammo, even when swapping
        # - From pickup (from_pickup=True): First pickup starts empty, swapping preserves ammo
        if from_pickup:
            if was_swapping:
                # When swapping between pickups, preserve current ammo (capped at new weapon's max)
                self.available_primary_abilities = min(current_ammo, self.max_primary_abilities)
            else:
                # When picking up a weapon from a pickup for the first time, start with 0 ammo
                self.available_primary_abilities = 0
        else:
            # When setting programmatically (e.g., in tests), always start with full ammo
            self.available_primary_abilities = self.max_primary_abilities

    def set_passive_ability(self, ability_name: str):
        self.passive_ability_name = ability_name
        self.passive_description = ""
        self.regenation = False
        self.regeneration_rate = 0.0
        self.mine_poop = False
        self.mine_wall = False
        self.can_get_angry = False

        if not ability_name:
            return

        ability_def = None
        for ability in get_passive_abilities():
            if ability["name"] == ability_name:
                ability_def = ability
                break
        if ability_def is None:
            return
        self.passive_ability_name = ability_def["name"]
        self.passive_description = ability_def["description"]
        ability_def["apply"](self)

    def changed_size(self):
        self.max_health = self._compute_max_health_for_size(self.size)
        self.health = min(self.health, self.max_health)
        self.width = self.size
        self.height = self.size
        self.update_damage_multiplier()

    def update_damage_multiplier(self):
        min_size = 9.0
        max_size = 80.0
        min_multiplier = 0.7
        max_multiplier = 1.5

        size_ratio = (self.size - min_size) / max(1.0, (max_size - min_size))
        self.damage_multiplier = max(min_multiplier, min(max_multiplier, min_multiplier + (max_multiplier - min_multiplier) * size_ratio))

        # Speed scales with size using the shared BASE_character defaults so other
        # projects can reuse the same fast-paced movement feel.
        self.speed = self.compute_speed_for_size(self.size)

    def _angle_to_mouse(self, mouse_pos):
        if mouse_pos is None:
            return 0.0
        dx = mouse_pos[0] - self.location[0]
        dy = mouse_pos[1] - self.location[1]
        return math.atan2(dy, dx)

    def _get_direction_info(self):
        """
        Determine which asset type (up/side) and transformations to use based on movement direction.
        Returns: (asset_type: str, rotation_angle: float, flip_horizontal: bool, flip_vertical: bool)
        
        Directions:
        - up: straight up (default up asset, no transform)
        - right: 90 degrees to the right (up asset, rotate -90° clockwise)
        - down: mirror vertical (up asset, flip vertical)
        - left: 90 degrees to the left (up asset, rotate 90° counter-clockwise)
        - up-right: default side asset (no transform)
        - down-right: 90 degrees to the right (side asset, rotate -90° clockwise)
        - down-left: mirror horizontal then 90 degrees to the left (side asset, flip horizontal, rotate 90° counter-clockwise)
        - up-left: mirror horizontal (side asset, flip horizontal)
        """
        dx, dy = self.last_movement_direction
        
        # If not moving, default to up direction
        if dx == 0 and dy == 0:
            return "up", 0.0, False, False
        
        # Normalize direction (should already be normalized, but ensure)
        dist = math.hypot(dx, dy)
        if dist > 0:
            dx /= dist
            dy /= dist
        
        # Determine which of 8 directions we're facing
        # Using thresholds to determine cardinal vs diagonal directions
        # For diagonal, we check if both components are significant
        abs_dx = abs(dx)
        abs_dy = abs(dy)
        
        # Threshold for considering a direction "diagonal" vs "cardinal"
        diagonal_threshold = 0.5  # cos(45°) ≈ 0.707, but we use 0.5 for easier classification
        
        if abs_dx < diagonal_threshold:
            # Primarily vertical movement
            if dy > 0:
                # Up
                return "up", 0.0, False, False
            else:
                # Down (mirror vertical)
                return "up", 0.0, False, True
        elif abs_dy < diagonal_threshold:
            # Primarily horizontal movement
            if dx > 0:
                # Right (90 degrees right)
                return "up", -90.0, False, False
            else:
                # Left (90 degrees left)
                return "up", 90.0, False, False
        else:
            # Diagonal movement - use side assets
            if dx > 0 and dy > 0:
                # Up-right (default side)
                return "side", 0.0, False, False
            elif dx > 0 and dy < 0:
                # Down-right (90 degrees right)
                return "side", -90.0, False, False
            elif dx < 0 and dy < 0:
                # Down-left (mirror horizontal then 90 degrees to the left = flip horizontal, rotate 90° counter-clockwise)
                return "side", 90.0, True, False
            else:  # dx < 0 and dy > 0
                # Up-left (mirror horizontal)
                return "side", 0.0, True, False

    def draw(self, screen: pygame.Surface, arena_height: float = None, camera=None):
        if not self._graphics_initialized:
            return
        # Get collision rect (unchanged - used for collision detection)
        rect = self.get_draw_rect(arena_height, camera)
        
        # Ensure rect has valid dimensions
        if rect.width <= 0 or rect.height <= 0:
            return
        
        # Client-side visual scale multiplier (only affects drawing, not collision)
        VISUAL_SCALE = 1.5  # Make cow appear 1.5x bigger visually
        
        # Calculate visual size for drawing (larger than collision rect)
        visual_width, visual_height = AssetHandler.get_visual_size(
            rect.width,
            rect.height,
            scale=VISUAL_SCALE,
        )
        
        draw_color = (200, 200, 255) if self.is_attacking else self.color
        if not self.is_alive:
            draw_color = (120, 120, 120)

        def fallback(surface):
            surface.fill(draw_color)
            pygame.draw.rect(surface, (30, 30, 30), surface.get_rect(), 2)

        # Use new category-based system or fall back to old system
        if self.is_alive:
            if self.skin_name and ".png" in self.skin_name:
                # Old format - use old system
                sprite, loaded = AssetHandler.get_image(
                    self.skin_name,
                    size=(visual_width, visual_height),  # Use visual size for drawing
                    fallback_draw=fallback,
                )
                # For old format, apply rotation like before
                if sprite is not None and loaded:
                    dx, dy = self.last_movement_direction
                    angle_rad = math.atan2(dx, dy)
                    angle_deg = -math.degrees(angle_rad)
                    sprite = pygame.transform.rotate(sprite, angle_deg)
            else:
                # New format - use category system with up/side assets
                # Determine which asset type and transformations to use
                asset_type, rotation_angle, flip_horizontal, flip_vertical = self._get_direction_info()

                # Use eating-specific assets if eating, otherwise normal assets
                asset_prefix = "eat" if self.is_eating else asset_type

                # Use current animation frame (0 when stopped, 1+ when moving)
                sprite, loaded, variant = AssetHandler.get_image_from_category(
                    "cows",
                    variant=self.cow_variant,  # Use stored variant or None for random
                    frame=self.animation_frame,  # Use current animation frame
                    size=(visual_width, visual_height),  # Use visual size for drawing
                    fallback_draw=fallback,
                    asset_prefix=asset_prefix,
                )
                # Store variant for consistency and count frames for animation
                if variant is not None:
                    if self.cow_variant is None:
                        self.cow_variant = variant
                    # Count frames across up/side and eat prefixes
                    # Use max to support variants that only define some prefixes
                    if self.animation_frame_count == 0:
                        prefixes = ["up", "side", "eat"]
                        counts = [
                            AssetHandler._count_frames("cows", variant, asset_prefix=prefix)
                            for prefix in prefixes
                        ]
                        frame_count = max(counts)
                        if frame_count > 0:
                            self.animation_frame_count = frame_count
                        else:
                            self.animation_frame_count = 1  # At least frame 0 exists
                
                # Apply transformations if asset was loaded
                if sprite is not None and loaded:
                    # Eating assets should not be direction-transformed
                    if self.is_eating:
                        rotation_angle = 0.0
                        flip_horizontal = False
                        flip_vertical = False
                    # Apply horizontal flip
                    if flip_horizontal:
                        sprite = pygame.transform.flip(sprite, True, False)
                    # Apply vertical flip
                    if flip_vertical:
                        sprite = pygame.transform.flip(sprite, False, True)
                    # Apply rotation
                    if rotation_angle != 0.0:
                        sprite = pygame.transform.rotate(sprite, rotation_angle)
        else:
            # Dead cow - use new category system
            sprite, loaded, variant = AssetHandler.get_image_from_category(
                "deadCows",
                variant=self.dead_cow_variant,  # Use stored variant or None for random
                frame=0,
                size=(visual_width, visual_height),  # Use visual size for drawing
                fallback_draw=fallback,
            )
            # Store variant for consistency (always store if we got one and don't have one)
            if variant is not None and self.dead_cow_variant is None:
                self.dead_cow_variant = variant
        
        if sprite is not None:
            # Center the sprite on the original collision rect center
            # Transformations have already been applied above for new format
            sprite_rect = sprite.get_rect(center=rect.center)
            screen.blit(sprite, sprite_rect)
        elif not loaded:
            pygame.draw.rect(screen, draw_color, rect)
            pygame.draw.rect(screen, (30, 30, 30), rect, 2)

        health_ratio = self.health / max(1.0, self.max_health)
        bar_width = self.size
        bar_height = 6
        bar_x = rect.x
        bar_y = rect.y - 10
        pygame.draw.rect(screen, (60, 60, 60), (bar_x, bar_y, bar_width, bar_height))
        pygame.draw.rect(screen, (80, 220, 80), (bar_x, bar_y, bar_width * health_ratio, bar_height))
