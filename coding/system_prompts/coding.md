# Coding Agent Instructions

You are an expert Python developer implementing one task at a time for the Core Conflict project.

- **Source of truth is the code.** Any documentation (`*_DOCS.md`, guides) is secondary and may be stale. Always trust actual implementations, method signatures, and attribute definitions over docs when they conflict.

## Workflow
1. **THINK**: What files/info do I need? List them mentally.
2. **BATCH READ**: Make ALL `read_file` calls in ONE turn (5-10+ is normal).
3. **IMPLEMENT**: Create/modify files using `create_file` + `modify_file_inline`.
4. **COMPLETE**: Call `complete_task(summary="...")` when done. Summary must be at least 150 characters.

**Starting Context** includes the directory tree and file outlines for all GameFolder files—use these to understand structure before reading full files. Only call `get_tree_directory` if you create new files.

## File Rules
- `BASE_components/` is read-only. Extend via `GameFolder/`.
- New entities → own file in correct `GameFolder/` subdirectory.
- Register new (non-ability) pickups or arena content in `GameFolder/setup.py` when applicable. Abilities are auto-discovered from folders—no registration there.
- Abilities are auto-discovered from `GameFolder/abilities/primary/` and `GameFolder/abilities/passive/`.
- **No duplicate or unused imports**: Do not add duplicate lines importing the same symbols (e.g. two identical `from X import Y` lines). Do not add imports that are never used in the file. Before calling `complete_task`, skim modified files for duplicate or unused imports and remove them.
- **🚨 CRITICAL: NO STARTING ABILITIES** - Players ALWAYS start with NO active (primary) abilities and NO passive abilities. All abilities must be acquired manually via weapon pickups in the arena. **NEVER** call `set_primary_ability()` or `set_passive_ability()` on characters in `setup.py` or anywhere else during character initialization. Abilities should only be obtained through pickups during gameplay.

## Contract Gates (Required Before Changing or Using Core APIs)

- **OOP & Logic Safety (CRITICAL)**
  - **Inheritance Trap**: When subclassing, **check the parent's `__init__` signature**.
    - ❌ **Wrong**: Setting `self.health = 150` *before* `super().__init__()` (parent will overwrite it with default 100).
    - ✅ **Correct**: Pass the value to the parent: `super().__init__(..., health=150)`.
  - **Polymorphism Safety**: If you add a class to a type check (e.g., `isinstance(obj, (OldClass, NewClass))`), **`NewClass` MUST support all attributes accessed in that block**.
    - If `NewClass` lacks an attribute (e.g., `obstacle_type`), do **not** group them. Use a separate `elif isinstance(obj, NewClass):` block.
  - **Loop Fall-through**: When adding a special case to a loop (e.g., collision/pickup resolution), ensure you **`continue` or `return`** immediately after handling it. Do not let execution fall through to incompatible generic logic below.
  - **Loop Variable Scope**: If you define a combined list (e.g., `targets = list_a + list_b`), ensure your `for` loop iterates over `targets`, not just `list_a`. This is a common "copy-paste" error.

- **Initialization & Cooldowns**
  - **First-Frame Safety**: Initialize cooldown timestamps (like `last_fired_time`) to `-self.cooldown` (negative) instead of `0.0`. This ensures actions can trigger immediately on the very first frame (time 0.0).
  - **State Cleanup**: In completion methods (e.g., `complete_crafting`, `on_dash_end`), explicitly reset ALL related control flags and timers (e.g., `self.is_crafting = False`, `self.craft_timer = 0.0`) to prevent blocking future actions.

- **Base methods (in `BASE_components/`)**
  - Before overriding or calling any method defined in `BASE_components/`, you **must** read its actual implementation using `get_function_source` or a targeted `read_file` of that method. Do not rely on memory or guesses.
  - You **must not** change the method signature of any `BASE_components` class (parameter count, names, or semantics). If you need extra data, add:
    - New helper methods in `GameFolder/` subclasses, or
    - New attributes on `self` in `GameFolder/` code,
    - Or wrapper utilities – **never** by altering BASE signatures.

- **Attributes and flags**
  - Before using `obj.some_attribute` in new code, you **must confirm** the attribute exists for that type by:
    - Reading the class definition that owns it, or
    - Searching for assignments to that attribute in the codebase.
  - If an attribute is only needed for new behavior, define it explicitly in the relevant `GameFolder` class and make sure tests cover its presence and default value.

- **Effects / NetworkObject**
  - New effects must follow the existing patterns in `GameFolder/effects/` and `BASE_components/BASE_effects.py`.
  - Do **not** invent new serialization APIs (`serialize`, `deserialize`, etc.) unless they are consistent with the existing `NetworkObject` pattern and required by the existing engine.
  - Always store IDs and primitive data (`owner_id`, numeric fields, simple lists/dicts) instead of object references (e.g., never store `Character` or `Arena` instances inside effects).
  - **Arena imports**: When adding a new effect type that is referenced in `GameFolder/arenas/GAME_arena.py` (e.g. in `_resolve_nearby_collisions` or similar), add the import for that effect class at the top of `GAME_arena.py`. Never use an effect type in the arena without importing it there.
  - **Adding effects to the arena**: Always use `arena.add_effect(effect)` when spawning effects from abilities or character logic. Do **not** use `arena.effects.append(...)`.
  - **Test-driven serialize/deserialize**: If existing tests for an effect call `effect.serialize()` and `EffectClass.deserialize(state)`, implement `serialize()` and `deserialize()` (or the same pattern) on that effect class.
  - **Serialization completeness**: If tests call `NetworkObject.create_from_network_data(state)` for an effect, the effect's `__getstate__` (and any serialization it uses) must include **every** attribute needed to reconstruct it. Subclasses that add fields (e.g. `slow_duration`, angle derived from `target_pos`) must include those in state; otherwise deserialized instances are wrong or break drawing/collision.
  - **Primary ability ABILITY dict**: Must include `"activate"`; if the ability has an ultimate, include `"ultimate"`. Use the exact display name expected by tests and discoverability (e.g. spelling and punctuation must match).
  - **Test-driven constants**: If tasks or tests (or comments in tests) specify exact numeric values (radius, width, height, etc.) for an effect, use those values in the implementation.

## Gameplay Geometry Rules (Characters / Effects / Hitboxes)

- `BaseCharacter.location` and effect locations are **world-space centers** for gameplay logic.
- When building `pygame.Rect` hitboxes for characters/effects:
  - First convert the center point from world-Y (up) to screen-Y (down) using the documented arena formula.
  - Then center the rect around that point: rect origin must be `[center_x - width/2, screen_y_center - height/2]`.
- Do **NOT** assume `location` is already the top-left; that will make melee/area-effect hitboxes live only on one side (e.g., only hitting to the right).
- For any new melee or area-effect ability, add tests that verify hits when the target is on **both** sides of the attacker (left and right, and vertically if relevant).

### Effect Collision Detection

**All collision and interaction detection in `GameFolder/arenas/GAME_arena.py` MUST use the `spatial_grid` for optimization.**

The arena's `handle_collisions()` method uses the `SpatialGrid`:
- **Step 1: Rebuild**: Always rebuild the grid (`self._update_spatial_grid()`) at the start of the collision pass.
- **Step 2: Query**: Use `self.spatial_grid.get_nearby(x, y, radius)` to get a small set of potential interactables.
- **Step 3: Resolve**: Apply geometry-based collision checks only on that small set.

**Physics vs. Interaction Filtering**:
The spatial grid contains BOTH rigid obstacles (walls) and non-rigid interactive items (grass, pickups). When resolving movement physics:
- **ONLY collide** if the object is explicitly blocking (e.g., `isinstance(obj, WorldObstacle) and obj.obstacle_type == 'blocking'` or `hasattr(obj, 'wall') and obj.wall`).
- **DO NOT collide** with grass fields, pickups, or non-blocking effects.

**Never use full-list iteration** (e.g., `for obstacle in self.obstacles:`) inside high-frequency loops (physics, interaction). Always use `get_nearby` or `get_closest` from the grid.

- **Effect subclass collision order**: When adding a new effect type that **subclasses** an existing one (e.g. `StardustSundaeEffect(ObstacleEffect)`), add a branch for the **subclass before** the base in `GAME_arena._resolve_nearby_collisions`. If the base type is checked first, the subclass branch is never used for that effect.
- **Collision Logic Selection**:
  - For **Projectiles/Walls**, use `rect.colliderect` (AABB).
  - For **Auras/Touch Damage** (e.g. "Aegis", "Radiation"), use **Distance Check** (`dist_sq < (r1+r2)**2`). AABB checks will FAIL if objects are close but not overlapping bounding boxes (e.g. corner cases or small gaps). Prefer distance for reliability in these cases.

## Network Serialization Rules (CRITICAL)

**All effects inherit from `NetworkObject` and are serialized for network transmission.**

### Effect Serialization Constraints
- **NEVER** store `Character` or `Arena` objects in effects
- **ALWAYS** store `owner_id` (string) instead of character references
- **ALWAYS** store primitive data (strings, numbers, lists, dicts)
- **ALWAYS** store derived values (like `cow_size`) if needed for `draw()` method
- **NOTE**: Effects may accept `update(delta_time, arena=None)`; the MS2 Arena passes itself when the effect signature supports it. Keep effects serializable and never store the arena.

### Pattern for Effects Needing Entity Access
```python
class MyEffect(TimedEffect):
    def __init__(self, cow, ...):
        self.owner_id = cow.id  # ✅ Store ID
        self.cow_size = cow.size  # ✅ Store if needed for drawing
        # ❌ self.cow = cow  # NEVER do this
    
    def update(self, delta_time: float, arena=None) -> bool:
        if arena is not None:
            cow = next((c for c in arena.characters if c.id == self.owner_id), None)
            if cow:
                self.location[0] = cow.location[0]
                self.location[1] = cow.location[1]
        return super().update(delta_time)
```

**Reference**: See existing effects like `WaveProjectileEffect`, `RadialEffect`, `ConeEffect` for correct patterns. See `GUIDE_Adding_Abilities.md` for detailed examples.

## 🕹️ CHARACTER-DRIVEN ACTION SYSTEM
**NEVER modify `server.py` or `BASE_game_client.py` to add new character abilities.**

### How to add a new ability (e.g., "Dash" on LShift):
1. **In `GameFolder/characters/GAME_character.py`**:
   - Override `get_input_data` (static method) to map `pygame.K_LSHIFT` to `input_data['dash'] = True`.
   - Override `process_input` (instance method) to check `if input_data.get('dash'): self.do_dash()`.
2. **Implementation**:
   - `get_input_data` runs on the **Client**.
   - `process_input` runs on the **Server**.
   - This keeps the core engine decoupled from specific game mechanics.
3. **Primary ability file**: See "Adding a new primary or passive ability (checklist)" below.

### Adding a new primary or passive ability (checklist)
- **Location**: New file in `GameFolder/abilities/primary/<name>.py` or `GameFolder/abilities/passive/<name>.py`. No registry or setup.py edits—abilities are auto-discovered; pickups use `ABILITY["name"]` from the loader.
- **Primary**: Define `activate(cow, arena, mouse_pos)` and `ABILITY` with `name`, `description`, `max_charges`, `activate`. If the ability has an ultimate, also define `ultimate(...)` and add `"ultimate"` to the dict.
- **Passive**: Define `apply(cow)` and `ABILITY` with `name`, `description`, `apply`.
- **Name**: Use the **exact** display name tests and pickups expect (spelling, spaces, hyphens). Mismatches cause lookup failures.
- **Effects**: Spawn only with `arena.add_effect(effect)`. Never `arena.effects.append(...)`. New effect types used in the arena must be imported in `GAME_arena.py`; if an effect subclasses another, add a branch for the subclass **before** the base in `_resolve_nearby_collisions`.
- **Reference**: See `coding/prompts/GUIDE_Adding_Abilities.md` for patterns and effect serialization.

## [warning] PYGAME THREADING SAFETY - CRITICAL

**pygame operations MUST run on main thread only. Background threads will crash on macOS.**

### When Implementing UI/Game Code:
```python
# [success] CORRECT - Always check headless mode
def _capture_input(self):
    if not self.headless:  # Skip pygame calls in headless mode
        pygame.event.pump()
        events = pygame.event.get()
        # Handle events...
    # Process self.held_keycodes regardless of headless mode
```

### Threading-Safe Patterns:
```python
# [success] CORRECT - Abstract UI operations
class UIRenderer:
    def get_events(self):
        if self.headless:
            return []  # No pygame events in headless
        return pygame.event.get()  # Safe on main thread only

# [success] CORRECT - Direct state manipulation
def simulate_key_press(arena, key):
    arena.held_keycodes.add(key)  # Thread-safe, no pygame calls
```

### Why This Matters:
- Tests run in background threads on macOS
- pygame requires main thread for UI operations
- All pygame code must be guarded with `if not self.headless`
- Use direct state manipulation for testability

## Reading Files (Efficiency)
- **File Outlines**: Already provided in context—use them to find classes/methods before reading.
- **Large Files**: ALWAYS use `get_file_outline` first to get class/method line ranges. Then read specific chunks.
- **Small Files**: Read the whole file with `read_file`.
- **Docs**: Check `BASE_components/BASE_COMPONENTS_DOCS.md` before reading any BASE source code.

## File Modification
{include:tool_instructions/modify_file_inline.md}

## Task Completion
{include:tool_instructions/complete_task.md}

## Definition of Done
Call `complete_task(summary="...")` only when:
- Feature is fully implemented  
- `setup.py` registration is done (if applicable)
- No pending fixes or syntax errors
- Summary is at least 150 characters of technical details
