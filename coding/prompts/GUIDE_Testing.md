# Testing Guide

## 0. VERIFY BEFORE TESTING

Read implementation first. Verify:
* `__init__` signature (parameters, order, types)
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
