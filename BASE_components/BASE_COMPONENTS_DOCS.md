# GenGame BASE Components Documentation

This document serves as the official API reference for the core GenGame engine. These components are located in `BASE_components/` and are **READ-ONLY**. All new game features must inherit from these classes in the `GameFolder/` directory.

---

## 🌍 Global Systems & Architecture

### Networking & Client/Server (IMMUTABLE)
GenGame uses a deterministic step-based networking model.
- **NEVER** modify `BASE_components/BASE_network.py` or the networking sections of `BASE_components/BASE_arena.py`.
- **NEVER** change how the client sends inputs (`run_client` method).
- **Control Flow**: 
    1. Clients capture raw inputs (keys, mouse) and send them to the Server.
    2. Server aggregates all player inputs into `self.latest_moves_dics`.
    3. Server broadcasts the aggregated inputs back to all clients.
    4. Both Server and Clients execute the exact same logic using `self.latest_moves_dics`.

### Input Handling
Inputs are received as a list of "moves" for each player ID.
- Access moves via `self.latest_moves_dics[player_id]`.
- Each move is a list: `[key_name, extra_data...]`.
- Standard keys: `"up"`, `"down"`, `"left"`, `"right"`, `"q"`.
- Mouse move: `["M_1", [world_x, world_y], left_pressed, middle_pressed, right_pressed]`.

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

The Arena is refactored into distinct steps. Override these in `GameFolder/arenas/GAME_arena.py` to insert custom logic.

### Step-based Execution
1. `collect_inputs()`: Fetches network/local inputs.
2. `apply_inputs()`: Processes `latest_moves_dics`. **OVERRIDE THIS** to handle custom keys (E, F, Right Click).
3. `update_world(delta_time)`: Runs physics, collisions, and state checks.
4. `render()`: Draws the scene.
5. `finalize_frame()`: Broadcasts sync data and clears moves.

### Custom Collision Logic
If your projectiles have special behaviors (pulling, persistent beams), you **MUST** override `handle_collisions` and call `super().handle_collisions(delta_time)` first.

---

## 4. UI (`BaseUI`)
**File**: `BASE_components/BASE_ui.py`

### Critical Methods
- `draw(characters, game_over, winner, respawn_timers)`: Main entry point.
- Renders circular health indicators in the top-right corner.
- Colors: Green (>60%), Yellow (>30%), Red (<30%).
