# TESTING SYSTEM (CONDENSED)

## 0. ABSOLUTE RULE: VERIFY BEFORE TESTING

Before writing **any** test, read the actual implementation.
You must verify:

* `__init__` signature (parameters, order, types)
* Method return types (`shoot()` → object, list, or None)
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
6. **Insufficient damage amounts** - Account for shield + health + defense reduction
7. **Single-step physics** - Physics methods may need multiple calls (velocity update → position update)
8. **Missing entity IDs** - Collision detection requires proper owner/victim IDs
9. **Coordinate system mismatches** - World Y-up vs Screen Y-down conversions
10. **Incomplete simulation** - Collision/landing may require multiple update cycles

---

## 3. GENERAL TEST RULES

* One concept per test
* Clear assertion messages (no bare `assert`)
* Fresh objects per test
* Use public APIs, not direct list/flag manipulation
* Test outcomes, not internal counters

---

## 4. CORE PATTERNS

### Weapons

Verify **all**:

* Projectile spawn
* Damage dealt
* Ammo consumption
* Cooldown enforcement
* Ammo depletion & pickup

### Projectiles

Verify:

* Movement
* Damage on hit
* Deactivation after collision

### Characters

Verify:

* Weapon integration
* Shield priority (shield → health)
* Shield regen timing
* Death blocks abilities

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
* **Projectile collision**: Requires proper owner/victim IDs and rect overlap

---

## 7. NEW FEATURE CHECKLIST

* Character size: `width == height == 30`
* Invulnerability: active after `respawn()`, expires after 8s
* Ammo scarcity: interval 12s, amounts [5,10,15], max 2
* Mirrored ammo spawns
* Weapons do NOT respawn on death

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
