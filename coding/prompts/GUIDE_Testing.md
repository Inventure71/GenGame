# Testing Guide

## 0. VERIFY BEFORE TESTING

Read implementation first. Verify:
* `__init__` signature (parameters, order, types)
* **API Existence**: Do not assume methods exist (e.g., `serialize()` vs `__getstate__()`). Check the class and its parents.
* **Initialization**: Verify constructor arguments (like `health`) are actually stored and not overwritten by `super().__init__`.
* Return types (e.g., `update()` → bool)
* Attribute names (never assume)
* State flags
* Inherited APIs via `BASE_COMPONENTS_DOCS.md`

---

## 1. TEST DISCOVERY

* Location: `GameFolder/tests/*.py`
* Functions: `test_*` with **ZERO parameters**
* ❌ `def test_x(arena):` → skipped
* ✅ `def test_x(): arena = Arena(...)`

---

## 2. COMMON FAILURES

1. Direct state assignment → use methods (`take_damage()`, not `health = 0`)
2. Assumed types/signatures → verify in code
3. Hardcoded values → use actual config
4. Reusing stateful objects → fresh per test
5. Wrong attribute names → verify in implementation
6. Insufficient damage → account for multipliers/cooldowns
7. Single-step physics → may need multiple calls
8. Missing entity IDs → required for collision detection
9. Coordinate mismatches → World Y-up vs Screen Y-down
10. Incomplete simulation → multiple update cycles needed
11. Type mismatches → sets vs dicts, lists vs tuples
12. Input format issues → missing `mouse_pos` or keys
13. **Execution order** → `handle_collisions()` moves character before effect checks
14. **First test in file** → If the first test in a file fails (import, setup, or headless), the rest of that file may not run. Ensure setup (arena, character, headless), imports, and any code run at import/creation (e.g. Character.__init__, AssetHandler) work with `headless=True`.

---

## 3. TEST RULES

* One concept per test
* Assertion messages required
* Fresh objects per test
* Use public APIs
* Test outcomes, not internals

## 4. VERIFICATION CHECKLIST

**Abilities/Effects:** Spawn, damage, cooldown, expiration
**Characters:** Abilities, size/health scaling, death

## 5. SIMULATION RULES

* Frame loops, not float accumulation
* Capture baseline after setup
* Physics may need multiple calls (state → apply)
* Collision needs full cycles
* Tick-based: large deltas split into 1/60s ticks
* Defense per tick, not total delta
* Track damage before resets

---

## 6. COORDINATES

* World Y: bottom → up | Screen Y: top → down
* Convert explicitly, leave margins
* Platform: `arena_height - location[1]`
* Effect collision: Uses circle methods with `cow.size / 2` radius
  - `RadialEffect`: `_circle_intersects_circle()`
  - `ConeEffect`: `_circle_intersects_triangle()`
  - `LineEffect`: `_circle_intersects_line()`
  - `WaveProjectileEffect`: `rect.colliderect()`

## 7. EXECUTION ORDER (CRITICAL)

`handle_collisions()` order:
1. `_resolve_obstacle_collisions()` → **MOVES** character
2. `_resolve_poops()` → May move character
3. `_apply_effects()` → Checks collisions
4. Pickup checks

**Pattern:**
```python
arena.handle_collisions()  # Let character settle
char_final = char.location[:]
effect = RadialEffect(char_final, ...)  # Place at final location
arena.add_effect(effect)
arena.handle_collisions()  # Test collision
```

**Use when:** Testing collisions with characters
**Skip when:** Testing standalone entities or character-to-character

## 8. FEATURE CHECKLIST

* Character: `width == height == 30`
* Abilities: one primary + one passive
* Grass: increases size, consumes food
* Poop: spawns obstacle, reduces size
* Safe zone: damages outside radius

## 9. COVERAGE

Per feature: Unit tests, integration tests, registration test

## 10. DEBUGGING FLOW

1. Read implementation (actual behavior)
2. Check damage: Shield → Health → Defense (per tick)
3. Verify physics (multiple cycles may be needed)
4. Confirm entity setup (IDs, positions, states)
5. Check coordinates (World vs Screen)
6. Validate collision prerequisites
7. Account for tick-based physics
8. Track state before resets
9. Handle entity death during simulation
10. Deplete shields for health visibility

**Damage pattern:** Large `delta_time` → 6 ticks of 0.0167s, defense per tick

---

## 11. TYPE & FORMAT COMPATIBILITY

**Test environment:**
- Arena: `WORLD_WIDTH/WORLD_HEIGHT` (2800x1800) in production; `Arena()` defaults to 1400x900 for local/headless tests
- `held_keys`: Python `set()` (not dict)
- `mouse_pressed`: `[False, False, False]` (Left, Middle, Right)
- Coordinate: `world_y = height - screen_y`
- Frame rate: 60 FPS (`delta_time = 0.016`)

**Key tests:**
1. Input type: `held_keys` as set, uses `in` operator
2. Arena dimensions: Test with `WORLD_WIDTH/WORLD_HEIGHT` and other sizes
3. Coordinates: World vs screen conversion
4. Mouse format: List with 3 booleans
5. Network sync: Fallback when class not loaded
6. Multiple keys: Simultaneous presses
7. Empty input: Safe defaults
8. Arrow/WASD: Equivalence
9. Dict structure: `'movement'`, `'mouse_pos'`, `'held_keys'`, `'mouse_buttons'`
10. Headless mode: No display calls
11. Network attributes: `hasattr()` checks, `__setstate__()` defaults
12. Platform collision: Production positions
13. Coordinate conversion: Both directions
14. Input throttling: 60 FPS rate
15. Key release: Movement stops

**Format:**
- `'movement': [int, int]`
- `'mouse_pos': [float, float]`
- `'held_keys': [keycodes...]` (list for serialization)
- `'mouse_buttons': [left, middle, right]`
- Optional: `'eat'`, `'dash'`, `'poop'`, `'swap'`, `'primary'`

---

## 12. SPATIAL GRID (GRAPH) TESTING

**CRITICAL**: The collision system now uses a `SpatialGrid` for optimization. 

- **Rebuild Requirement**: If you move entities manually in a test (e.g., `char.location = [100, 100]`), the `spatial_grid` will NOT know about the move until `arena._update_spatial_grid()` or `arena.handle_collisions()` is called.
- **Query Verification**: When testing if an object is "reachable" or "collidable," ensure it has been added to the grid. The `Arena` class handles this automatically in its update loop, but manual tests may need to trigger a rebuild.
- **Filtering**: If a test fails to find an object, check if the `filter_func` in `get_nearby` or `get_closest` is correctly identifying the target class.

**Pattern for Manual Collision Testing:**
```python
char.location = [spawn_x, spawn_y]
arena.add_character(char)
# Trigger rebuild so the grid knows where the character is
arena._update_spatial_grid() 

# Now queries will work
nearby = arena.spatial_grid.get_nearby(spawn_x, spawn_y, 100)

## 13. TROUBLESHOOTING SPECIFIC FAILURES

| Symptom | Probable Cause | Check |
| :--- | :--- | :--- |
| **Action fails on first frame** | Cooldown blocking | Is `last_use_time` initialized to `0.0`? If `current_time` is also `0.0`, `0 < cooldown` is True. Init to `-cooldown`. |
| **"Expected X, got 0"** | Early return / Blocking | Is a state flag (e.g., `crafting_timer`) stuck > 0 because the previous action didn't clear it? |
| **AttributeError: 'X' has no attribute 'serialize'** | Missing Interface | Does class X inherit from a parent but fail to implement a method required by the test? `NetworkObject` often requires explicit `serialize/deserialize`. |
| **Test says "Overlapping" but `colliderect` fails** | Hitbox Precision | Are they physically touching or just close? For Auras/Shields, use distance checks (`dist < r1+r2`) instead of `colliderect`. |
| **"Spawn on death" fails** | Execution Order | Does `arena.update` call `super()` (respawning the char) *before* checking if it died? Move death checks *before* `super().update`. |
| **Effect didn't modify target** | Loop Scope | Did you define `targets = a + b` but write `for x in a:`? |
