# GenGame BASE Components Documentation

This document serves as the official API reference for the core GenGame engine. These components are located in `BASE_components/` and are **READ-ONLY**. All new game features must inherit from these classes in the `GameFolder/` directory.

**⚠️ Important**: This documentation focuses only on the public API that game developers can use and modify through inheritance. Internal systems (networking, serialization) are not documented as they cannot be modified.

---

## 🌍 Global Systems & Architecture

### Local Single-Player Gameplay
GenGame runs as a local single-player game with direct input handling.
- **Input Handling**: Direct keyboard and mouse input processing.
- **Control Flow**:
    1. Capture local inputs (keys, mouse) from pygame events.
    2. Apply inputs directly to the local character.
    3. Update game simulation and physics.
    4. Render the scene.

### Input Handling
Inputs are captured directly from pygame events.
- Standard keys: Arrow keys/WASD for movement, Space for jump, Q for drop weapon.
- Mouse: Left click for shooting, position for aim direction.
- Special keys: E/F for special abilities.

### Coordinate Systems
- **World Coordinates (Logic)**: Y-axis points **UP**. `[0, 0]` is bottom-left. Used for physics and object locations.
- **Screen Coordinates (Pygame)**: Y-axis points **DOWN**. `[0, 0]` is top-left. Used for rendering.
- **Conversion Methods**: Use `self.screen_to_world(x, y)` and `self.world_to_screen(x, y)` in the Arena class.

---

## 1. Character (`BaseCharacter`)
**File**: `BASE_components/BASE_character.py`

### Key Attributes
- `self.location`: `[x, y]` in **World Coordinates**.
- `self.health` / `self.max_health`: Current/Max HP (default 100.0).
- `self.lives`: Fixed at 3 (Immutable).
- `self.weapon`: The currently equipped `BaseWeapon` or `None`.
- `self.on_ground`: Boolean flag updated by physics.
- `self.vertical_velocity`: Current upward/downward velocity (used for jumping and falling).
- **Flight System**: 
  - `self.flight_time_remaining`: Current flight fuel (max 3.0 seconds).
  - `self.needs_recharge`: If True, flight is disabled until landing.
  - `self.is_currently_flying`: True when actively flying (pressing UP/DOWN while airborne).
  - Flight only activates when: airborne + falling/at peak + pressing UP or DOWN + has flight energy.
- **Status Effects**: `self.physics_inverted`, `self.speed_multiplier`, `self.jump_height_multiplier`.

### Critical Methods
- `move(direction, platforms)`: Updates position. Handles jumping, flying, and status effects.
- `update(delta_time, platforms, arena_height)`: Handles gravity, flight recharge, and multiplier recovery.
- `shoot(target_pos)` / `secondary_fire(target_pos)` / `special_fire(target_pos, is_holding)`: Spawning logic for different fire modes.

---

## 2. Platform (`BasePlatform`)
**File**: `BASE_components/BASE_platform.py`

### Key Attributes
- `self.rect`: Pygame Rect in screen coordinates (y-down).
- `self.float_x` / `self.float_y`: Float precision position for smooth movement.
- `self.original_x` / `self.original_y`: Starting position for return behavior.
- `self.being_pulled`: Flag set by arena during pull effects (Black Hole, Tornado).
- `self.health` / `self.is_destroyed`: Platform health system.

### Critical Methods
- `move(dx, dy)`: Moves the platform by delta values.
- `return_to_origin(delta_time, return_speed)`: Gradually moves back to original position.
- `take_damage(amount)`: Reduces health and marks as destroyed at 0.

---

## 3. Weapon & Projectile
**Files**: `BASE_components/BASE_weapon.py`, `BASE_components/BASE_projectile.py`

### Weapon Methods
- `shoot(...)`: Standard fire. **MUST OVERRIDE** to return custom projectiles.
- `secondary_fire(...)`: Optional override for alternate fire.
- `special_fire(...)`: Optional override for channeled or special abilities.

### Projectile Attributes
- `self.location`: `[x, y]` in **World Coordinates**.
- `self.active`: If False, it is removed in the next frame.
- `self.owner_id`: ID of the character who fired it (used to prevent friendly fire).
- `self.direction`: Normalized vector `[x, y]` for movement direction.
- `self.speed`: Movement speed in pixels per frame at 60 FPS.
- `self.damage`: Damage dealt on hit.
- `self.is_persistent`: If True, projectile is not removed on collision (for beams, clouds, etc.).
- `self.skip_collision_damage`: If True, Arena won't auto-deal damage (for custom collision logic).

---

## 4. Arena (`BaseArena`)
**File**: `BASE_components/BASE_arena.py`

The Arena handles the main game loop. Override methods in `GameFolder/arenas/GAME_arena.py` to insert custom logic.

### Game Loop Execution
1. `step()`: Main game loop method called every frame.
2. `_capture_input()`: Captures local keyboard and mouse input.
3. `_update_simulation(delta_time)`: Updates physics, projectiles, and game state.
4. `render()`: Draws the scene.
5. `update(delta_time)`: Headless simulation update (no rendering).

**Note**: Tests may use `update_world(delta_time)` which is an alias for `update(delta_time)`.

### Key Attributes
- `self.characters`: List of all `BaseCharacter` objects in the game.
- `self.platforms`: List of all `BasePlatform` objects.
- `self.projectiles`: List of all active `BaseProjectile` objects.
- `self.weapon_pickups`: List of weapons available for pickup.
- `self.lootpool`: Dict mapping weapon names to their factory functions.

### Custom Collision Logic
**Required for special projectiles**: If your projectiles have special behaviors (pulling, persistent beams, custom damage), you **MUST**:
1. Override `handle_collisions(delta_time)` in your Arena class.
2. Call `super().handle_collisions(delta_time)` first to handle standard collisions.
3. Process your special projectiles after the base call.
4. Set `projectile.is_persistent = True` to prevent auto-removal.
5. Set `projectile.skip_collision_damage = True` to handle damage manually.

---

## 5. UI (`BaseUI`)
**File**: `BASE_components/BASE_ui.py`

### Critical Methods
- `draw(characters, game_over, winner, respawn_timers)`: Main entry point for UI rendering.
- Renders circular health indicators in the top-right corner.
- Health bar colors: Green (>60%), Yellow (>30%), Red (<30%).
- Displays game over screen with winner information.
