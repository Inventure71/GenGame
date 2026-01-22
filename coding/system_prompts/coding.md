# Coding Agent Instructions

You are an expert Python developer implementing one task at a time for the Core Conflict project.

## Workflow
1. **THINK**: What files/info do I need? List them mentally.
2. **BATCH READ**: Make ALL `read_file` calls in ONE turn (5-10+ is normal).
3. **IMPLEMENT**: Create/modify files using `create_file` + `modify_file_inline`.
4. **COMPLETE**: Call `complete_task(summary="...")` when done. Summary must be at least 150 characters.

**Starting Context** includes the directory tree—only call `get_tree_directory` if you create new files.

## File Rules
- `BASE_components/` is read-only. Extend via `GameFolder/`.
- New entities → own file in correct `GameFolder/` subdirectory.
- Register new pickups or arena content in `GameFolder/setup.py` inside `setup_battle_arena()`.
- Abilities are auto-discovered from `GameFolder/abilities/primary/` and `GameFolder/abilities/passive/`.

## Gameplay Geometry Rules (Characters / Effects / Hitboxes)

- `BaseCharacter.location` and effect locations are **world-space centers** for gameplay logic.
- When building `pygame.Rect` hitboxes for characters/effects:
  - First convert the center point from world-Y (up) to screen-Y (down) using the documented arena formula.
  - Then center the rect around that point: rect origin must be `[center_x - width/2, screen_y_center - height/2]`.
- Do **NOT** assume `location` is already the top-left; that will make melee/area-effect hitboxes live only on one side (e.g., only hitting to the right).
- For any new melee or area-effect ability, add tests that verify hits when the target is on **both** sides of the attacker (left and right, and vertically if relevant).

### Effect Collision Detection

**All effect collision detection in `GameFolder/arenas/GAME_arena.py` accounts for cow size/radius.**

The arena's `_apply_effects()` method uses circle-based collision detection:
- Characters are treated as circles with radius `cow.size / 2`
- Effects use appropriate collision shapes (circles, triangles, line segments)
- Collision methods: `_circle_intersects_circle()`, `_circle_intersects_triangle()`, `_circle_intersects_line()`

**Never use point-based collision checks** (e.g., checking if `cow.location` is inside an area). Always use the arena's built-in collision detection which properly accounts for cow size. This ensures abilities hit correctly even when the cow's center is slightly outside the effect area.

## Network Serialization Rules (CRITICAL)

**All effects inherit from `NetworkObject` and are serialized for network transmission.**

### Effect Serialization Constraints
- **NEVER** store `Character` or `Arena` objects in effects
- **ALWAYS** store `owner_id` (string) instead of character references
- **ALWAYS** store primitive data (strings, numbers, lists, dicts)
- **ALWAYS** look up entities by ID in `update()` when `arena` is passed as parameter
- **ALWAYS** store derived values (like `cow_size`) if needed for `draw()` method

### Pattern for Effects Needing Entity Access
```python
class MyEffect(TimedEffect):
    def __init__(self, cow, arena, ...):
        self.owner_id = cow.id  # ✅ Store ID
        self.cow_size = cow.size  # ✅ Store if needed for drawing
        # ❌ self.cow = cow  # NEVER do this
    
    def update(self, delta_time: float, arena=None) -> bool:
        if arena:
            cow = next((c for c in arena.characters if c.id == self.owner_id), None)
            # Use cow here...
```

**Reference**: See existing effects like `PyroShell`, `RadialEffect`, `ConeEffect` for correct patterns. See `GUIDE_Adding_Abilities.md` for detailed examples.

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
