# Core Conflict BASE Components Documentation

This document is the API reference for the **lowest‑level** Core Conflict engine pieces. These live in `BASE_components/` and are **READ‑ONLY**. All gameplay logic, abilities, effects, and game-specific visuals should be implemented in `GameFolder/` by extending these base classes.

**Guiding rule:** Base = low‑level primitives + immutable systems (game loop, safe zone). GameFolder = specialization.

---

## 🌍 Architecture Overview

### What lives in BASE
- Immutable systems: game loop, safe zone updates
- Low‑level primitives: `BaseCharacter`, `BasePlatform`, `BaseWorldPlatform`, `BaseEffect`, `TimedEffect`, `BaseUI`, `BasePickup`
- Shared helpers: movement/animation state, collision geometry helpers, pickup rendering
- Network serialization support via `NetworkObject` (in `BASE_components/BASE_network.py`)
  - ⚠️ **CRITICAL**: `NetworkObject` strips `animation_frame`, `animation_timer`, and `animation_frame_count` during transmission. Subclasses MUST provide defaults or handle their absence if `draw()` relies on them.

### What lives in GameFolder
- Concrete gameplay systems: MS2 abilities/effects, pickups, obstacles, grass
- Collision rules and item pickup logic
- Game-specific UI rendering
- Character behavior and ability logic

---

## Coordinate System
- **World Coordinates (Logic)**: Y‑axis points **UP**. `[0, 0]` is bottom‑left.
- **Screen Coordinates (Pygame)**: Y‑axis points **DOWN**. `[0, 0]` is top‑left.
- **Conversion (center-based)**: `screen_y_center = arena_height - world_y`, then rect origin is `screen_y_center - object_height / 2`

Avoid hardcoding arena height; always use the current arena height when converting.

---

## 1. Character (`BaseCharacter`)
**File**: `BASE_components/BASE_character.py`

### Purpose
A minimal, network‑serializable character that supports movement, damage, and basic drawing. Gameplay actions (abilities, dashes, eating, etc.) must be added in `GameFolder/characters/GAME_character.py`.

### Key Attributes
- `self.id`: Character identifier (defaults to `name`)
- `self.name` / `self.description` / `self.image`: Character metadata
- `self.location`: `[x, y]` in world coordinates (y‑up)
- `self.width` / `self.height`: Size of the character
- `self.speed`: Base movement speed (default 3.0)
- `self.health` / `self.max_health`: Current/Max health (default 100.0)
- `self.lives`: Lives remaining (`MAX_LIVES`, default 1)
- `self.is_alive` / `self.is_eliminated`: Life state
- `self.color`: RGB color tuple for drawing (default (220, 220, 220))
- `self.last_arena_height`: Cached arena height for rect calculations
- Speed scaling constants: `SPEED_FAST_MIN`, `SPEED_SLOW_MAX`, `SPEED_MIN_SIZE`, `SPEED_MAX_SIZE`
- Speed instance vars: `speed_fast_min`, `speed_slow_max`, `speed_min_size`, `speed_max_size`
- Animation state: `last_movement_direction`, `is_moving`, `animation_frame`, `animation_timer`, `animation_frame_count`, `animation_speed`, `_prev_location`

### Key Methods
- `get_input_data(held_keys, mouse_buttons, mouse_pos)` (static)
  - Returns `movement` + `mouse_pos` and passes through raw `held_keys` and `mouse_buttons`
- `process_input(input_data, arena)`
  - Handles base movement, delegates actions to `handle_actions`
- `handle_actions(input_data, arena)`
  - **Hook** for GameFolder logic (abilities, dash, eat, etc.)
- `move(direction, arena)`
  - Updates position and clamps to arena bounds
- `take_damage(amount)` / `heal(amount)` / `die()` / `respawn(respawn_location, arena)`
- `get_rect(arena_height)` → `pygame.Rect`
  - Returns collision rect in screen coordinates
- `get_draw_rect(arena_height, camera)` → `pygame.Rect`
  - Returns draw rect with optional camera support
- `compute_speed_for_size(size)` → `float`
  - Shared helper for size-based speed scaling (smaller = faster)
- `_update_movement_state(dx, dy)`
  - Updates `last_movement_direction` and `is_moving`
- `_update_client_animation(delta_time)`
  - Updates animation frames (uses `is_eating` if defined)
- `update(delta_time, arena)`
  - Updates character state (caches arena height)
- `draw(screen, arena_height, camera)`
  - Draws character with health bar
- `init_graphics()`
  - Initializes graphics resources (safe to call multiple times)
- `__setstate__(state)`
  - Deserialization support (restores state, initializes graphics)

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
- `self.projectiles`: Projectile list (GameFolder usage)
- `self.weapon_pickups` / `self.ammo_pickups`: Pickup lists
- `self.safe_zone`: `SafeZone` instance
- `self.enable_safe_zone`: If True, applies safe‑zone damage
- `self.current_time`: Elapsed game time
- `self.spatial_grid`: `SpatialGrid` instance for optimized collision/interaction lookup
- `self.tick_accumulator` / `self.tick_interval`: Fixed timestep accumulator and interval (internal)
- `self.safe_damage_times`: Dict tracking last damage time per character
- `self.safe_damage_interval`: Damage interval (default 1.0s)
- `self.game_over` / `self.winner`: Game state
- `self.respawn_timer`: Dict tracking respawn timers per character
- `self.respawn_delay` / `self.allow_respawn`: Respawn configuration
- `self.held_keycodes`: Set of currently held keys
- `self.running`: Main loop flag
- `self.headless`: If True, no pygame display
- `self.screen` / `self.clock`: Pygame objects (None if headless)

### Constants
- `WORLD_WIDTH = 2800`, `WORLD_HEIGHT = 1800`: World dimensions
- `TICK_RATE = 60`: Fixed update rate

### Key Methods
- `step()` / `run()`: Main loop
- `_capture_input()`: Captures pygame input for local play
- `update(delta_time)`: Updates safe zone, effects, characters, handles collisions
- `handle_collisions()`: **Override in GameFolder** for game-specific collisions
- `handle_respawns(delta_time)`: Handles character respawning (if enabled)
- `check_winner()`: Checks for game over condition
- `_update_effects(delta_time)`: Updates and removes expired effects
- `_apply_safe_zone_damage()`: Applies safe zone damage to characters outside
- `_apply_knockback(cow, source_location, distance)`: Shared knockback helper
- `_push_out_of_rect(cow, obstacle_rect)`: Shared collision resolution helper
- `_circle_intersects_circle(...)` / `_circle_intersects_triangle(...)` / `_circle_intersects_line(...)`: Geometry helpers
- `add_character(character)` / `add_platform(platform)` / `add_effect(effect)`: Add entities
- `render()`: Minimal render loop (override for visuals)

---

## 3. Effects (`BaseEffect`, `TimedEffect`)
**File**: `BASE_components/BASE_effects.py`

### Purpose
Low‑level effect primitives. No gameplay shapes or damage logic exist here.

### Base Classes
- `BaseEffect`: network‑serializable object with `location`, `update`, `draw`
  - `update(delta_time)` → `bool`: Returns `True` if expired (default `False`)
  - `update(delta_time, arena=None)` → `bool`: Optional signature; GAME_arena uses signature inspection to detect if the effect accepts an arena parameter, and if so, passes itself (the arena instance) when calling `update()`
  - `draw(screen, arena_height, camera)`: Override for rendering
- `TimedEffect`: base effect with lifetime tracking
  - `update(delta_time)` → `bool`: Returns `True` when `age >= lifetime`
  - `update(delta_time, arena=None)` → `bool`: Optional signature; same arena parameter support as `BaseEffect`
  - `remaining()` → `float`: Returns remaining lifetime
  - Attributes: `lifetime`, `age`

### Network Serialization
All effects inherit from `NetworkObject` (via `BaseEffect`). When implementing effects:
- **Store only primitive data**: strings, numbers, lists, dicts
- **Store `owner_id` (string)**, not character objects
- **Effects may accept `update(delta_time, arena=None)`**; the MS2 Arena uses signature inspection to detect if the effect accepts an arena parameter, and if so, passes itself (the arena instance) when calling `update()`. The arena is never stored in the effect, only passed as a parameter.
- See `GUIDE_Adding_Abilities.md` for detailed serialization patterns

All concrete effects (cones, shockwaves, walls, etc.) should live in `GameFolder/effects/` in one class per file (for example `coneeffect.py`, `radialeffect.py`, `lineeffect.py`, `waveprojectileeffect.py`, `obstacleeffect.py`, `zoneindicator.py`).

---

## 4. Safe Zone (`SafeZone`)
**File**: `BASE_components/BASE_safe_zone.py`

### Purpose
Shrinking zone that damages characters outside its radius. This is immutable.

### Key Attributes
- `center`: `[x, y]` center (shifts periodically)
- `target_center`: Target position for center shifts
- `radius`: Current radius (shrinks over time)
- `min_radius`: Minimum radius (20% of smaller dimension)
- `damage`: Damage per interval (increases over time: 1.0 + min(5.0, elapsed / 30.0))
- `shrink_rate`: Radius shrink speed (default 4.0 units/sec)
- `center_shift_timer` / `center_shift_interval`: Center shift timing (default 12.0s)
- `elapsed`: Total elapsed time
- `width` / `height`: Arena dimensions

### Key Methods
- `update(delta_time)`: Shrinks radius, shifts center, increases damage
- `contains(x, y)` → `bool`: Checks if point is inside safe zone

---

## 5. Platform (`BasePlatform`, `BaseWorldPlatform`)
**File**: `BASE_components/BASE_platform.py`

### Purpose
Low‑level platform/obstacle type for collision and rendering.

### Key Attributes
- `self.rect`: pygame.Rect (screen space)
- `self.float_x` / `self.float_y`: float position for smooth movement
- `self.original_x` / `self.original_y`: Original spawn position
- `self.width` / `self.height`: Platform dimensions
- `self.color`: RGB color tuple (default (100, 100, 100))
- `self.health`: Platform health (default 100.0)
- `self.is_destroyed`: Destruction flag

### Key Methods
- `move(dx, dy)`: Move platform by offset
- `return_to_origin(delta_time, return_speed)`: Gradually return to original position
- `take_damage(amount)`: Reduce health, set `is_destroyed` if health <= 0
- `init_graphics()`: Initialize graphics (thread-safe, safe to call multiple times)
- `draw(screen, arena_height, camera)`: Draw platform

### `BaseWorldPlatform`
World-space platform that stores a `world_center` and converts to screen-space for drawing.

Key method:
- `get_draw_rect(arena_height, camera)` → `pygame.Rect`: Converts world center to a screen-space rect

---

## 6. Pickups (`BasePickup`)
**File**: `BASE_components/BASE_pickups.py`

### Purpose
Generic pickup with world-space location, activation state, and basic rendering. GameFolder should extend this to add game-specific behavior and labels.

### Key Attributes
- `self.location`: `[x, y]` in world coordinates
- `self.width` / `self.height`: Size of the pickup sprite
- `self.pickup_radius`: Collision radius
- `self.is_active`: Active flag
- `self.color`: Draw color
- `self.label`: Optional label text

### Key Methods
- `get_pickup_rect(arena_height)` → `pygame.Rect`: Collision rect
- `get_label()` → `str`: Override to supply label text
- `draw(screen, arena_height, camera)`: Renders pickup with optional label

---

## 7. Camera (`BaseCamera`)
**File**: `BASE_components/BASE_camera.py`

### Purpose
World-to-screen camera for large arenas. Keeps all server logic in absolute world coordinates while the client renders a viewport.

### Key Attributes
- `world_width` / `world_height`: World dimensions
- `view_width` / `view_height`: Viewport dimensions
- `center`: `[x, y]` camera center in world coordinates (clamped to bounds)

### Key Methods
- `set_center(x, y)`: Set camera center (clamped to world bounds)
- `set_world_size(world_width, world_height)`: Update world dimensions
- `set_view_size(view_width, view_height)`: Update viewport dimensions
- `get_viewport()` → `(left, bottom, right, top)`: Get viewport bounds
- `world_to_screen_point(x, y)` → `(screen_x, screen_y)`: Convert world to screen coords
- `screen_to_world_point(x, y)` → `(world_x, world_y)`: Convert screen to world coords
- `world_center_rect_to_screen(center_x, center_y, width, height)` → `pygame.Rect`: Convenience for drawing
- `_clamp_center()`: Internal method to clamp center to valid bounds

---

## 8. UI (`BaseUI`)
**File**: `BASE_components/BASE_ui.py`

### Purpose
Minimal UI hook. GameFolder should implement real UI rendering.

### Key Attributes
- `self.screen`: Pygame surface for drawing
- `self.arena_width` / `self.arena_height`: Arena dimensions

### Key Methods
- `__init__(screen, arena_width, arena_height)`: Initialize UI with screen and dimensions
- `draw(characters, game_over, winner, respawn_timers, local_player_id, network_stats)`
  - Hook for UI rendering (default no-op)

---

## 9. Asset Handler (`AssetHandler`)
**File**: `BASE_components/BASE_asset_handler.py`

### Purpose
Centralized asset loading system with caching, fallback support, and category-based organization. Supports both legacy flat file structure and new category/variant structure.

### Asset Organization
Assets are organized in `GameFolder/assets/` with two supported structures:

**New Structure (Recommended)**:
```
assets/
  category/
    variant/
      0.png, 1.png, ... N.png
```
- Categories: `cows`, `deadCows`, `slowObstacles`, `blockObstacles`, `grass`, `background`
- Variants: Random selection per object for visual variety
- Frames: Numbered 0 to N for animations (single frame if N=0 only)

**Legacy Structure (Fallback)**:
- Flat files in `assets/` root (e.g., `ERBA.png`, `mucca0.png`)

### Key Methods

#### Image Loading
- `get_image(asset_name, size=None, fallback_draw=None, fallback_tag=None)` → `(surface, loaded)`
  - Loads a single image from legacy flat file structure
  - Returns tuple: `(pygame.Surface or None, bool loaded)`
  - Supports fallback drawing function if asset not found

- `get_image_from_category(category, variant=None, frame=0, size=None, fallback_draw=None, fallback_tag=None)` → `(surface, loaded, variant)`
  - Loads image from category/variant structure
  - If `variant=None`, randomly selects a variant and stores it
  - Returns tuple: `(pygame.Surface or None, bool loaded, str variant_used)`

- `get_image_with_alpha(asset_name, size=None, alpha=255, ...)` → `(surface, loaded)`
  - Loads image with alpha transparency control

#### Animation Loading
- `get_animation(base_name, frame_count, size=None, fallback_draw=None, fallback_tag=None)` → `(frames, loaded)`
  - Legacy method: loads frames named `{base_name}0.png` to `{base_name}{N}.png`
  - Returns tuple: `(List[pygame.Surface], bool loaded)`

- `get_animation_from_category(category, variant=None, size=None, fallback_draw=None, fallback_tag=None)` → `(frames, loaded, variant)`
  - Loads animation from category/variant structure
  - Automatically counts frames (0.png, 1.png, ...)
  - If `variant=None`, randomly selects a variant
  - Returns tuple: `(List[pygame.Surface], bool loaded, str variant_used)`

#### Utility Methods
- `get_random_variant(category)` → `Optional[str]`
  - Returns a random variant name from a category, or `None` if category doesn't exist

- `get_font(font_name, size, bold=False, italic=False)` → `pygame.font.Font`
- `get_sys_font(font_name, size, bold=False, italic=False)` → `pygame.font.Font`
- `render_text(text, font_name, size, color, ...)` → `pygame.Surface`

### Features
- **Caching**: All assets are cached by key (name/size/variant combinations)
- **Transparency**: Automatically preserves alpha channels with `convert_alpha()`
- **Fallback Support**: Graceful degradation with custom drawing functions
- **Variant Consistency**: Selected variants are stored per object for visual consistency
- **Backward Compatible**: Legacy flat file structure still supported

### Usage Example
```python
from BASE_components.BASE_asset_handler import AssetHandler

# New category-based system (random variant)
sprite, loaded, variant = AssetHandler.get_image_from_category(
    "cows",
    variant=None,  # Random selection
    frame=0,
    size=(30, 30),
    fallback_draw=lambda s: s.fill((255, 0, 0))
)

# Animation from category
frames, loaded, variant = AssetHandler.get_animation_from_category(
    "slowObstacles",
    variant=None,  # Random selection
    size=(50, 50)
)

# Legacy flat file (backward compatibility)
image, loaded = AssetHandler.get_image("ERBA.png", size=(100, 100))
```

---

## 10. Spatial Grid (`SpatialGrid`)
**File**: `BASE_components/BASE_spatial.py`

### Purpose
Shared spatial partitioning engine for high-performance collision and interaction queries. Used by both client (prediction) and server (authoritative logic).

### Key Methods
- `clear()`: Wipes the grid (called before rebuild)
- `add(obj)`: Adds an object to all cells it overlaps. Supports `WorldObstacle`, `GrassField`, `AbilityPickup`, `Character`, and `Effect` types.
- `get_nearby(x, y, radius, filter_func=None)`: Returns a `set` of objects within cells overlapping the search circle.
- `get_closest(x, y, radius, filter_func=None)`: Returns `(object, distance)` for the single closest item matching the criteria.

### Best Practices
- **Rebuild Frequency**: The grid is typically rebuilt once per frame at the start of the collision pass to ensure move-heavy frames are perfectly accurate.
- **Filtering**: Use `filter_func` to narrow down results (e.g., `lambda o: isinstance(o, GrassField)`) instead of filtering the returned set manually.
- **Opt-in Collisions**: When using `get_nearby` for physics, always check for specific blocking types (e.g., `obstacle_type == 'blocking'`) to avoid colliding with non-physical interactive objects like grass.

---

## GameFolder Extension Points
Concrete gameplay lives in these modules:
- `GameFolder/characters/GAME_character.py`: MS2 cow logic and abilities
- `GameFolder/abilities/`: one file per primary/passive ability with descriptions
- `GameFolder/arenas/GAME_arena.py`: collisions, pickup handling, effect damage
- `GameFolder/effects/`: concrete cone, radial, line, wave, and obstacle effects (one class per module)
- `GameFolder/world/GAME_world_objects.py`: obstacles + grass
- `GameFolder/pickups/GAME_pickups.py`: ability pickups
- `GameFolder/ui/GAME_ui.py`: MS2 UI

Keep BASE minimal and extend in GameFolder.
