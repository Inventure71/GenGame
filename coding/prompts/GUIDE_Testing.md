# TESTING SYSTEM (CONDENSED)

## 0. ABSOLUTE RULE: VERIFY BEFORE TESTING

Before writing **any** test, read the actual implementation.
You must verify:

* `__init__` signature (parameters, order, types)
* Method return types (e.g., `update()` → bool for expiration)
* Attribute names (`self.horizontal_velocity` ≠ `vx`)
* State flags (`is_stationary`, `is_alive`, etc.)
* Inherited APIs via `BASE_COMPONENTS_DOCS.md`

**Never assume names or behavior. Always confirm in code.**

---

## 1. TEST DISCOVERY (CRITICAL)

* Tests live in `GameFolder/tests/*.py`
* Functions **must**:

  * start with `test_`
  * take **ZERO parameters**
* pytest fixtures or parameters → **test is skipped**

```python
# ❌ Skipped
def test_x(arena): ...

# ✅ Discovered
def test_x(): arena = Arena(...)
```

---

## 2. MOST COMMON FAILURES (MEMORIZE)

1. Direct state assignment instead of methods

   * ❌ `health = 0` → ✅ `take_damage()` / `die()`
2. Assumed constructor or return types
3. Hardcoded config values (arena size, cooldowns)
4. Reusing stateful objects across tests
5. Wrong attribute names
6. **Insufficient damage amounts** - Account for size-based multipliers or cooldown gating
7. **Single-step physics** - Physics methods may need multiple calls (velocity update → position update)
8. **Missing entity IDs** - Collision detection requires proper owner/victim IDs
9. **Coordinate system mismatches** - World Y-up vs Screen Y-down conversions
10. **Incomplete simulation** - Collision/landing may require multiple update cycles
11. **Type mismatches** - Sets vs dicts, lists vs tuples, wrong input formats
12. **Input format incompatibilities** - Missing `mouse_pos` or raw input passthrough keys
13. **Execution order mismatch** - Placing entities before obstacle resolution moves characters
    - **Symptom**: Test places effect/pickup at character location, but no collision detected
    - **Cause**: `_resolve_obstacle_collisions()` moves character BEFORE effect/pickup checks
    - **Fix**: Call `handle_collisions()` first, capture final location, then place entities

---

## 3. GENERAL TEST RULES

* One concept per test
* Clear assertion messages (no bare `assert`)
* Fresh objects per test
* Use public APIs, not direct list/flag manipulation
* Test outcomes, not internal counters

---

## 4. CORE PATTERNS

### Abilities & Effects

Verify **all**:

* Effect spawn
* Damage dealt (when applicable)
* Cooldown enforcement per target
* Effect expiration / cleanup

### Characters

Verify:

* Ability integration (primary + passive)
* Size/health scaling on grass eat and poop
* Death eliminates player (single life)

---

## 5. TIME & SIMULATION RULES

* Use integer frame loops, not float accumulation
* Capture baseline **after setup, before action**
* Allow multiple frames for collisions/events
* **Physics methods often require multiple calls** - First call updates state (velocity), second call applies it (position)
* **Collision detection needs full simulation cycles** - Single `handle_collisions()` may not be enough
* **Tick-based physics breaks large deltas** - `update_world(delta_time)` splits into fixed-size ticks (1/60s)
* **Defense applied per tick, not per total delta** - Large deltas get multiple defense reductions
* **Track damage before state resets** - When resetting entity state for controlled measurement, capture damage first

```python
for _ in range(max_frames):
    update()
    if event(): break
```

**Physics Pattern:**
```python
# Single call may only update velocity, not position
method()  # Updates internal state
method()  # Applies state change
```

**Tick-Based Damage Pattern:**
```python
# Large delta_time gets broken into multiple ticks
# Each tick applies defense separately
# Total damage = sum of (damage_per_tick - defense) * num_ticks
```

---

## 6. COORDINATES & PRECISION

* World Y: bottom → up
* Screen Y: top → down
* Convert explicitly
* Leave margins (avoid 1px gaps)
* **Platform collision**: Character feet position = `arena_height - location[1]`
* **Effect collision**: Requires proper owner/victim IDs. Collision detection uses circle-based methods that account for cow radius (`cow.size / 2`), not just center points:
  - `RadialEffect`: `_circle_intersects_circle()` (cow circle vs effect circle)
  - `ConeEffect`: `_circle_intersects_triangle()` (cow circle vs triangle)
  - `LineEffect`: `_circle_intersects_line()` (cow circle vs line segment)
  - `WaveProjectileEffect`: `rect.colliderect()` (rectangle collision)
  - When testing, verify hits work when cow's center is near but not inside the effect area

---

## 6.5 EXECUTION ORDER & STATE MUTATIONS (CRITICAL)

**When testing collisions, effects, or pickups, execution order matters.**

### The Problem

`handle_collisions()` processes collisions in a specific order:
1. `_resolve_obstacle_collisions(cow)` - **MOVES** character if overlapping obstacles
2. `_resolve_poops(cow)` - May move character
3. `_apply_effects(cow)` - Checks collisions (character may have moved!)
4. Pickup checks - Happen after obstacle resolution

If you place an effect/pickup at the character's initial location, but the character gets moved by obstacle resolution, the collision won't be detected.

### The Solution

**Pattern 1: For collision/effect tests**
```python
# Step 1: Setup character
arena = Arena(400, 300, headless=True)
char = Character("TestCow", "Test", "", [200.0, 150.0])
arena.add_character(char)

# Step 2: Let obstacle resolution happen
arena.handle_collisions()

# Step 3: Capture final location
char_final_location = char.location[:]

# Step 4: Place entity at final location
effect = RadialEffect(char_final_location, radius=60, ...)
arena.add_effect(effect)

# Step 5: Test actual behavior
arena.handle_collisions()
assert char.health < initial_health
```

**Pattern 2: For pickup tests**
```python
# Step 1: Setup character
arena = Arena(800, 600, headless=True)
char = Character("TestCow", "Test", "", [0.0, 0.0])
arena.add_character(char)

# Step 2: Let obstacle resolution happen
arena.handle_collisions()
char_final_location = char.location[:]

# Step 3: Place or move pickup to final location
pickup = next((p for p in arena.weapon_pickups if p.ability_type == "primary"), None)
if pickup is None:
    pickup = AbilityPickup(PRIMARY_ABILITY_NAMES[0], "primary", char_final_location[:])
    arena.weapon_pickups.append(pickup)
else:
    pickup.location = char_final_location[:]

# Step 4: Test actual behavior
arena.handle_collisions()
assert char.primary_ability_name == pickup.ability_name
```

### When to Use This Pattern

**ALWAYS use this pattern when:**
- Testing effect collisions with characters
- Testing pickup collisions with characters
- Placing entities at the same location as characters
- Testing any collision that depends on character position

**You DON'T need this pattern when:**
- Testing effects that don't depend on character position
- Testing character-to-character collisions (both move together)
- Testing standalone entity behavior (no character involved)

---

## 7. NEW FEATURE CHECKLIST

* Character size: `width == height == 30`
* Ability slots: one primary + one passive
* Grass: eating increases size and consumes food
* Poop: spawns obstacle effect and reduces size
* Safe zone: damages outside radius

---

## 8. PYGAME SAFETY

* Always use `Arena(..., headless=True)`
* No pygame events in tests
* Never run pygame code in threads

---

## 9. REQUIRED COVERAGE

Per feature:

* Unit tests
* Integration tests (arena + characters)
* Registration test (loot pool)

---

## 10. TEST DEBUGGING FLOW

When tests fail:

1. **Read the implementation** - Understand actual behavior, not assumed behavior
2. **Check damage calculations** - Shield → Health → Defense reduction (per tick for large deltas)
3. **Verify physics simulation** - May need multiple update cycles
4. **Confirm entity setup** - IDs, positions, initial states
5. **Check coordinate conversions** - World vs Screen coordinates
6. **Validate collision prerequisites** - Overlap, active state, owner IDs
7. **Account for tick-based physics** - Large `delta_time` values are split into fixed-size ticks
8. **Track state before resets** - When resetting entity state for measurement, capture values first
9. **Handle entity death during long simulations** - Entities may die during warmup/initialization; reset them before final measurement
10. **Deplete shields for health damage visibility** - Set `shield = 0` to test health damage directly

**Systematic Debugging Pattern:**
1. Read implementation to understand actual behavior
2. Identify tick-based vs continuous calculations
3. Calculate expected values accounting for tick splitting and per-tick reductions
4. If entities die during simulation, reset state before final measurement
5. Track cumulative values (damage, state) before any resets
6. Sum pre-reset + post-reset values for total

**Damage Calculation Pattern:**
- Large delta_time (e.g., 0.1s) → broken into 6 ticks of 0.0167s
- Each tick: `(damage_per_sec * tick_interval) - defense`
- Total: `damage_per_tick * num_ticks`
- When resetting entity state mid-test, track damage before reset and add to post-reset damage
- Shield depletion pattern: Set `entity.shield = 0` before testing health damage

---

## 11. CRITICAL TYPE & FORMAT COMPATIBILITY TESTS

**⚠️ ALWAYS TEST THESE - They catch production-breaking bugs before deployment**

**Test Environment Requirements:**
- Arena dimensions: `1400x900` (production dimensions from `server.py:247`)
- `held_keys`: Python `set()` type (matches `BASE_game_client.py:172`)
- `mouse_pressed`: Python `list` with 3 booleans `[False, False, False]` (Left, Middle, Right)
- Coordinate conversion: `world_y = height - screen_y` (matches `BASE_game_client.py:212`)
- Frame rate: 60 FPS (`delta_time = 0.016`)

### Input Handling Tests

1. **Input Type Compatibility - `get_input_data()`**
   - Call `Character.get_input_data()` with `held_keys` as a **set** (not dict), matching `BASE_game_client.py:172-219`
   - Verify it uses `in` operator (`pygame.K_a in held_keys`), not subscript notation (`held_keys[pygame.K_a]`)

2. **Arena Dimensions - Hardcoded Values**
   - Test with arena `width=1400, height=900` (production dimensions from `server.py:247`)
   - Verify no hardcoded `900` or `1400` values break when dimensions differ
   - Test with different arena sizes to catch hardcoded assumptions

3. **Coordinate System Conversion**
   - Test mouse position conversion using `world_y = height - screen_y` (matches `BASE_game_client.py:212`)
   - Verify collision detection uses world coordinates, not screen coordinates
   - Test platform collision with production platform positions from `setup.py:77-90`

4. **Mouse Input Format**
   - Pass `mouse_pressed` as list `[False, False, False]` (Left, Middle, Right) matching `BASE_game_client.py:173`
   - Verify `mouse_buttons[0]` is left click, `mouse_buttons[2]` is right click
   - Test with all combinations of mouse button states

5. **Network State Synchronization**
   - Test `get_input_data()` when `Character` class is `None` or not loaded yet (matches `BASE_game_client.py:218-222`)
   - Verify fallback input dict structure matches expected format
   - Test entity creation from network data (simulate `NetworkObject.create_from_network_data()`)

6. **Multiple Key Press Detection**
   - Test `get_input_data()` with multiple keys in set simultaneously (e.g., `{pygame.K_d, pygame.K_w, pygame.K_SPACE}`)
   - Verify all actions are detected correctly, not just the first one
   - Test diagonal movement combinations

7. **Empty Input State**
   - Test `get_input_data()` with empty set `set()` and all-false mouse list
   - Verify returns safe defaults (no movement, no actions) without errors
   - Test that missing keys don't crash `process_input()`

8. **Arrow Key vs WASD Equivalence**
   - Test both `pygame.K_a`/`pygame.K_LEFT` and `pygame.K_d`/`pygame.K_RIGHT` produce same movement
   - Verify arrow keys work identically to WASD
   - Test all movement key pairs

9. **Input Data Dictionary Structure**
   - Verify returned dict has keys: `'movement'`, `'mouse_pos'`, `'held_keys'`, `'mouse_buttons'`
   - Verify optional action keys appear only when triggered: `'eat'`, `'dash'`, `'poop'`, `'primary'`
   - Verify `'movement'` is `[int, int]` and `'mouse_pos'` is `[float, float]`

10. **Headless Mode Compatibility**
    - Test with `headless=True` (server environment)
    - Verify no pygame display/event calls that would crash in headless mode
    - Test that all game logic works without display

11. **Attribute Existence After Network Sync**
    - Test character methods after creating from network data (simulate `NetworkObject.create_from_network_data()`)
    - Verify `hasattr()` checks for optional attributes like `shield`, `max_shield` before access
    - Test `__setstate__()` initializes missing attributes with defaults

12. **Platform Collision with Production Arena**
    - Test character landing on platforms using actual platform positions from `setup.py:77-90` with `1400x900` arena
    - Verify collision detection works with production platform layout
    - Test edge cases (platform boundaries, gaps)

13. **World-to-Screen Coordinate Conversion**
    - Test drawing/rendering uses `screen_y = arena_height - world_y - object_height` formula
    - Verify characters render at correct screen positions from world coordinates
    - Test coordinate conversion in both directions

14. **Input Throttling Compatibility**
    - Test input processing at 60 FPS rate (`0.016` second intervals, matches `BASE_game_client.py:215`)
    - Verify no errors when called rapidly in succession
    - Test that throttling doesn't drop critical inputs

15. **Key Release Handling**
    - Test that keys removed from set (via `held_keys.discard()`) are no longer detected
    - Verify movement stops when key is released, not just when pressed
    - Test rapid key press/release sequences

### Format Compatibility Tests

16. **Input Dictionary Key Name Consistency**
    - Verify both BASE and GAME use `'movement'` (no legacy `'move'`)
    - Test that `process_input()` reads `input_data.get('movement', [0, 0])`
    - Ensure `'mouse_pos'` is always present and is a list `[x, y]`

17. **Primary Action Value Type**
    - Test that `'primary'` uses a mouse position list when present
    - Verify `process_input()` handles missing `'primary'` safely
    - Ensure `'primary'` matches the click world position

18. **Raw Input Passthrough**
    - Verify `'held_keys'` and `'mouse_buttons'` are present
    - Confirm they are lists (serializable) and reflect current input state

19. **Method Override Completeness**
    - Test that `GAME_character.get_input_data()` extends BASE and preserves raw input keys
    - Verify all BASE functionality is preserved or explicitly replaced, not accidentally broken
    - Test inheritance chain works correctly

20. **Network Serialization Attribute Preservation**
    - Test that custom attributes (like `size`, `dashes_left`, ability names) are preserved through `__getstate__()`/`__setstate__()`
    - Verify `__setstate__()` initializes missing attributes with defaults
    - Test round-trip serialization (serialize → deserialize → verify state)

21. **Default Parameter Values in Overrides**
    - Test `update()` method with different arena sizes (world larger than viewport)
    - Verify logic does not assume `1400x900`
    - Defaults might hide bugs - always test with explicit values

22. **List vs Tuple Type Consistency**
    - Test that coordinate lists `[x, y]` are consistently lists, not tuples
    - Verify `location`, `mouse_pos`, and `movement` are lists (mutable)
    - Affects network sync and mutation - tuples can't be modified

23. **Mouse Button Index Bounds**
    - Test `mouse_pressed` list access with indices 0, 1, 2 (Left, Middle, Right)
    - Verify `mouse_buttons[0]` and `mouse_buttons[2]` don't crash when list has fewer than 3 elements
    - Should always be `[False, False, False]` but test defensive coding

**Critical Input Format:**

- `'movement': [x, y]`
- `'mouse_pos': [mouse_x, mouse_y]`
- `'held_keys': [keycodes...]`
- `'mouse_buttons': [left, middle, right]`
- Optional: `'eat'`, `'dash'`, `'poop'`, `'primary'`
