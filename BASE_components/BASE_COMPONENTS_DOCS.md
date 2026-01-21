# Core Conflict BASE Components Documentation

This document is the API reference for the **lowest‑level** Core Conflict engine pieces. These live in `BASE_components/` and are **READ‑ONLY**. All gameplay logic, abilities, effects, pickups, and visuals should be implemented in `GameFolder/` by extending these base classes.

**Guiding rule:** Base = low‑level primitives + immutable systems (game loop, safe zone). GameFolder = specialization.

---

## 🌍 Architecture Overview

### What lives in BASE
- Immutable systems: game loop, safe zone updates
- Low‑level primitives: `BaseCharacter`, `BasePlatform`, `BaseEffect`, `TimedEffect`, `BaseUI`
- Network serialization support via `NetworkObject` (in `BASE_files/BASE_network.py`)

### What lives in GameFolder
- Concrete gameplay systems: MS2 abilities/effects, pickups, obstacles, grass
- Collision rules and item pickup logic
- UI rendering
- Character behavior and ability logic

---

## Coordinate System
- **World Coordinates (Logic)**: Y‑axis points **UP**. `[0, 0]` is bottom‑left.
- **Screen Coordinates (Pygame)**: Y‑axis points **DOWN**. `[0, 0]` is top‑left.
- **Conversion Formula**: `screen_y = arena_height - world_y - object_height`

Avoid hardcoding arena height; always use the current arena height when converting.

---

## 1. Character (`BaseCharacter`)
**File**: `BASE_components/BASE_character.py`

### Purpose
A minimal, network‑serializable character that supports movement, damage, and basic drawing. Gameplay actions (abilities, dashes, eating, etc.) must be added in `GameFolder/characters/GAME_character.py`.

### Key Attributes
- `self.location`: `[x, y]` in world coordinates (y‑up)
- `self.width` / `self.height`: Size of the character
- `self.speed`: Base movement speed
- `self.health` / `self.max_health`: Current/Max health
- `self.lives`: Lives remaining (`MAX_LIVES`, default 1)
- `self.is_alive` / `self.is_eliminated`: Life state

### Key Methods
- `get_input_data(held_keys, mouse_buttons, mouse_pos)`
  - Returns `movement` + `mouse_pos` and passes through raw `held_keys` and `mouse_buttons`
- `process_input(input_data, arena)`
  - Handles base movement, delegates actions to `handle_actions`
- `handle_actions(input_data, arena)`
  - **Hook** for GameFolder logic (abilities, dash, eat, etc.)
- `move(direction, arena)`
  - Updates position and clamps to arena bounds
- `take_damage(amount)` / `heal(amount)` / `die()` / `respawn()`

**Note**: Do not put game‑specific abilities here. Extend in GameFolder.

---

## 2. Arena (`Arena`)
**File**: `BASE_components/BASE_arena.py`

### Purpose
Immutable game loop and safe‑zone management. Override in GameFolder for gameplay rules (collisions, effects, pickups).

### Key Attributes
- `self.characters`: Active characters
- `self.platforms`: Platforms/obstacles
- `self.effects`: Active effects (base list only)
- `self.safe_zone`: `SafeZone` instance
- `self.enable_safe_zone`: If True, applies safe‑zone damage

### Key Methods
- `step()` / `run()`: Main loop
- `_capture_input()`: Captures pygame input for local play
- `update(delta_time)`: Updates safe zone, effects, characters
- `handle_collisions()`: **Override in GameFolder**
- `render()`: Minimal render loop (override for visuals)

---

## 3. Effects (`BaseEffect`, `TimedEffect`)
**File**: `BASE_components/BASE_effects.py`

### Purpose
Low‑level effect primitives. No gameplay shapes or damage logic exist here.

### Base Classes
- `BaseEffect`: network‑serializable object with `location`, `update`, `draw`
- `TimedEffect`: base effect with lifetime tracking

All concrete effects (cones, shockwaves, walls, etc.) should live in `GameFolder/effects/`.

---

## 4. Safe Zone (`SafeZone`)
**File**: `BASE_components/BASE_safe_zone.py`

### Purpose
Shrinking zone that damages characters outside its radius. This is immutable.

### Key Attributes
- `center`: `[x, y]` center
- `radius`: Current radius
- `damage`: Damage per interval

### Key Methods
- `update(delta_time)`
- `contains(x, y)`

---

## 5. Platform (`BasePlatform`)
**File**: `BASE_components/BASE_platform.py`

### Purpose
Low‑level platform/obstacle type for collision and rendering.

### Key Attributes
- `self.rect`: pygame.Rect (screen space)
- `self.float_x` / `self.float_y`: float position for smooth movement

---

## 6. Camera (`BaseCamera`)
**File**: `BASE_components/BASE_camera.py`

### Purpose
World-to-screen camera for large arenas. Keeps all server logic in absolute world coordinates while the client renders a viewport.

### Key Methods
- `set_center(x, y)`: Follow a target in world space (clamped to world bounds)
- `world_to_screen_point(x, y)`: Convert world coords to screen coords
- `screen_to_world_point(x, y)`: Convert screen coords to world coords
- `world_center_rect_to_screen(center_x, center_y, width, height)`: Convenience for drawing

---

## 7. UI (`BaseUI`)
**File**: `BASE_components/BASE_ui.py`

### Purpose
Minimal UI hook. GameFolder should implement real UI rendering.

---

## GameFolder Extension Points
Concrete gameplay lives in these modules:
- `GameFolder/characters/GAME_character.py`: MS2 cow logic and abilities
- `GameFolder/abilities/`: one file per primary/passive ability with descriptions
- `GameFolder/arenas/GAME_arena.py`: collisions, pickup handling, effect damage
- `GameFolder/effects/GAME_effects.py`: cone, radial, line, wave, poop effects
- `GameFolder/world/GAME_world_objects.py`: obstacles + grass
- `GameFolder/pickups/GAME_pickups.py`: ability pickups
- `GameFolder/ui/GAME_ui.py`: MS2 UI

Keep BASE minimal and extend in GameFolder.
