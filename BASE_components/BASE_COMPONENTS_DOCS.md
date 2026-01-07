# GenGame BASE Components Documentation

This document serves as the official API reference for the core GenGame engine. These components are located in `BASE_components/` and are **READ-ONLY**. All new game features must inherit from these classes in the `GameFolder/` directory.

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
- **Flight System**: `self.flight_time_remaining`, `self.needs_recharge`, `self.is_currently_flying`.
- **Status Effects**: `self.physics_inverted`, `self.speed_multiplier`, `self.jump_height_multiplier`.

### Critical Methods
- `move(direction, platforms)`: Updates position. Handles jumping, flying, and status effects.
- `update(delta_time, platforms, arena_height)`: Handles gravity, flight recharge, and multiplier recovery.
- `shoot(target_pos)` / `secondary_fire(target_pos)` / `special_fire(target_pos, is_holding)`: Spawning logic for different fire modes.

---

## 2. Weapon & Projectile
**Files**: `BASE_components/BASE_weapon.py`, `BASE_components/BASE_projectile.py`

### Weapon Methods
- `shoot(...)`: Standard fire. **MUST OVERRIDE** to return custom projectiles.
- `secondary_fire(...)`: Optional override for alternate fire.
- `special_fire(...)`: Optional override for channeled or special abilities.

### Projectile Attributes
- `self.location`: `[x, y]` in **World Coordinates**.
- `self.active`: If False, it is removed in the next frame.
- `self.owner_id`: ID of the character who fired it.

---

## 3. Arena (`BaseArena`)
**File**: `BASE_components/BASE_arena.py`

The Arena handles the main game loop. Override methods in `GameFolder/arenas/GAME_arena.py` to insert custom logic.

### Game Loop Execution
1. `step()`: Main game loop method called every frame.
2. `_capture_input()`: Captures local keyboard and mouse input.
3. `_update_simulation(delta_time)`: Updates physics, projectiles, and game state.
4. `render()`: Draws the scene.

### Custom Collision Logic
If your projectiles have special behaviors (pulling, persistent beams), you **MUST** override `handle_collisions` and call `super().handle_collisions(delta_time)` first.

---

## 4. UI (`BaseUI`)
**File**: `BASE_components/BASE_ui.py`

### Critical Methods
- `draw(characters, game_over, winner, respawn_timers)`: Main entry point.
- Renders circular health indicators in the top-right corner.
- Colors: Green (>60%), Yellow (>30%), Red (<30%).
