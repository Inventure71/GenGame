# GenGame BASE Components Documentation

This document serves as the official API reference for the core GenGame engine. These components are located in `BASE_components/` and are **READ-ONLY**. All new game features must inherit from these classes in the `GameFolder/` directory.

---

## 🌍 Global Constants & Systems

### Coordinate Systems
The game uses two different coordinate systems. Mixing them is the #1 cause of bugs.
- **World Coordinates (Logic)**: Y-axis points **UP**. `[0, 0]` is the bottom-left. Used for physics, gravity, and object locations.
- **Screen Coordinates (Pygame)**: Y-axis points **DOWN**. `[0, 0]` is the top-left. Used for rendering and `pygame.Rect` objects.
- **Conversion Formula**: `screen_y = arena_height - world_y - object_height`

### Common Pitfalls
- **Vertical Velocity**: Use `self.vertical_velocity` (a float scalar). Do **NOT** use `self.velocity` (which doesn't exist).
- **Health**: Use `self.health`. Do **NOT** use `self.hp`.
- **Attribute Discovery**: If you aren't sure an attribute exists on a child class, use `getattr(obj, 'attr_name', default_value)`.

---

## 1. Character (`BaseCharacter`)
**File**: `BASE_components/BASE_character.py`

The base class for all players and NPCs.

### Key Attributes
- `self.location`: `[x, y]` in **World Coordinates**.
- `self.vertical_velocity`: Float scalar for up/down movement.
- `self.health` / `self.max_health`: Current and max HP (default 100.0).
- `self.lives`: Fixed at 3 (Immutable).
- `self.scale_ratio`: Multiplier for visual size and collision box (default 1.0).
- `self.on_ground`: Boolean flag updated by physics.
- `self.weapon`: The currently equipped `BaseWeapon` instance or `None`.

### Critical Methods
- `update(delta_time, platforms, arena_height)`: Called every frame. Handles gravity and stamina regeneration.
- `apply_gravity(arena_height, platforms)`: Core physics logic. **Note**: Checks `plat.is_solid` if it exists on the platform.
- `take_damage(amount)`: Reduces health after applying `defense` logic. Triggers `die()` if health <= 0.
- `jump()`: Sets `vertical_velocity` to `jump_height`. Only works if `on_ground` is True.
- `shoot(target_pos)`: Centers the projectile spawn on the character and calls `weapon.shoot()`.

---

## 2. Weapon (`BaseWeapon`)
**File**: `BASE_components/BASE_weapon.py`

The base class for all equippable items.

### Key Attributes
- `self.damage`: Base damage dealt by projectiles.
- `self.cooldown`: Time in seconds between shots.
- `self.projectile_speed`: Speed of spawned projectiles.
- `self.is_equipped`: Flag for whether it's held or on the ground.

### Critical Methods
- `can_shoot()`: Returns True if the cooldown has elapsed. Uses `time.time()`.
- `shoot(owner_x, owner_y, target_x, target_y, owner_id)`: **MUST OVERRIDE** in the GAME version to return specific projectile classes. The base implementation returns a generic `BaseProjectile`.
- `draw(screen, arena_height)`: Renders the weapon as a pickup when on the ground.

---

## 3. Projectile (`BaseProjectile`)
**File**: `BASE_components/BASE_projectile.py`

### Key Attributes
- `self.location`: `[x, y]` in **World Coordinates**.
- `self.direction`: Normalized `[x, y]` vector.
- `self.active`: Boolean. If False, the Arena removes it in the next frame.
- `self.owner_id`: ID of the character who fired it (to prevent self-harm).

### Critical Methods
- `update(delta_time)`: Moves the projectile based on `speed` and `direction`.
- `draw(screen, arena_height)`: Handles the World -> Screen conversion for rendering.

---

## 4. Platform (`BasePlatform`)
**File**: `BASE_components/BASE_platform.py`

### Key Attributes
- `self.rect`: A `pygame.Rect` in **Screen Coordinates**.
- `self.health`: Platforms can be destructible.
- `self.is_destroyed`: If True, it is ignored by physics and rendering.

### Critical Methods
- `take_damage(amount)`: Reduces health and sets `is_destroyed`.
- **Note for GAME version**: If you want characters to fall through a platform (e.g. "Glitched Platform"), add an `is_solid` attribute to your `Platform` class. The physics engine in `BaseCharacter` checks for this.

---

## 5. Arena (`BaseArena`)
**File**: `BASE_components/BASE_arena.py`

The main game controller.

### Key Attributes
- `self.characters`: List of all active players.
- `self.platforms`: List of all platforms (Index 0 is usually the floor).
- `self.projectiles`: List of active projectiles.
- `self.lootpool`: Dictionary mapping weapon names to classes/factories.

### Critical Methods
- `handle_collisions(delta_time)`: The most complex method. Handles:
    1. Projectile vs Character damage.
    2. Projectile vs Platform destruction.
    3. Character vs Weapon pickup.
- `register_weapon_type(name, weapon_provider)`: Adds a weapon to the spawn list.
- `manage_weapon_spawns(delta_time)`: Periodically picks a random platform and spawns a random weapon from the lootpool.
- **Tip for GAME version**: If your weapon has "special" projectiles (like black holes or lasers), you **MUST** override `handle_collisions` in `GAME_arena.py` to add custom collision logic for those specific types.

---

## 6. UI (`BaseUI`)
**File**: `BASE_components/BASE_ui.py`

Handles the heads-up display.

### Critical Methods
- `draw(characters, game_over, winner, respawn_timers)`: The main entry point for rendering the HUD.
- `draw_character_info(...)`: Renders the health bar, lives, and current weapon for a player.

