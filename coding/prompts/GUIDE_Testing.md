# TESTING SYSTEM

## 🚨 CRITICAL: VERIFY IMPLEMENTATION DETAILS FIRST 🚨

**Before writing ANY test, you MUST verify these in the actual implementation:**

1. **Constructor signature**: Check `__init__` for exact parameters and order
2. **Method return types**: What does `shoot()` return? Single object, list, or None?
3. **Attribute names**: Search for `self.` assignments (don't assume `vx` exists if it's `horizontal_velocity`)
4. **State flag names**: Find actual boolean names (`is_stationary` not `is_on_floor`)
5. **API methods**: Use `BASE_COMPONENTS_DOCS.md` for Character/Weapon/Projectile methods

**Never assume standard names. Always read the implementation.**

---

## 🔥 TOP 5 MOST COMMON TEST FAILURES 🔥

1. **Direct state manipulation** → Use proper methods instead of setting attributes
   - Example: Setting `health = 0` won't trigger death logic; use `take_damage()` or `die()`

2. **Hardcoded values** → Tests with different configurations fail
   - Example: Hardcoded arena dimensions break coordinate conversion; pass as parameters

3. **Assumed constructor signatures** → Tests crash on object creation
   - Always read `__init__` before creating objects in tests

4. **Assumed return types** → Code expects list but gets single object
   - Check what methods actually return before using the result

5. **Stateful objects** → Reusing objects between tests causes unexpected behavior
   - Create fresh instances or explicitly reset state between tests

---

## STRUCTURE
- Tests in `GameFolder/tests/*.py`
- Auto-discovered and run by `BASE_tests.py`
- Functions must start with `test_` and take no parameters

## TEST FILE TEMPLATE
```python
"""
Tests for [Feature Name]
"""

from GameFolder.characters.GAME_character import Character
from GameFolder.weapons.YourWeapon import YourWeapon
from GameFolder.projectiles.YourProjectile import YourProjectile

def test_creation():
    """Test object creation and properties."""
    obj = YourClass(...)
    assert obj.property == expected, "message"

def test_behavior():
    """Test specific behavior."""
    obj = YourClass(...)
    result = obj.method()
    assert result == expected, "message"
```

## WEAPON TESTING PATTERNS
```python
def test_weapon_creation():
    gun = YourWeapon()
    assert gun.name == "Name"
    assert gun.damage > 0
    assert not gun.is_equipped
    assert gun.ammo == gun.max_ammo  # Starts with full ammo

def test_weapon_shooting():
    gun = YourWeapon()
    initial_ammo = gun.ammo
    projectiles = gun.shoot(100, 100, 200, 100, "owner")
    assert isinstance(projectiles, list)
    assert len(projectiles) == expected_count
    assert all(p.damage == gun.damage for p in projectiles)
    assert gun.ammo == initial_ammo - gun.ammo_per_shot  # Ammo consumed

def test_weapon_cooldown():
    gun = YourWeapon()
    shot1 = gun.shoot(100, 100, 200, 100, "owner")
    shot2 = gun.shoot(100, 100, 200, 100, "owner")  # Immediate retry
    assert shot1 is not None
    assert shot2 is None  # Blocked by cooldown

def test_weapon_ammo_depletion():
    gun = YourWeapon()
    # Shoot until out of ammo
    shots = 0
    while gun.ammo >= gun.ammo_per_shot:
        result = gun.shoot(100, 100, 200, 100, "owner")
        if result is not None:
            shots += 1
        gun.last_shot_time = 0  # Reset cooldown
    
    # Should not shoot when out of ammo
    final_shot = gun.shoot(100, 100, 200, 100, "owner")
    assert final_shot is None
    assert gun.ammo < gun.ammo_per_shot

def test_weapon_ammo_pickup():
    gun = YourWeapon()
    gun.ammo = 5  # Reduce ammo
    gun.add_ammo(10)
    assert gun.ammo == 15
    
    # Should not exceed max_ammo
    gun.add_ammo(1000)
    assert gun.ammo == gun.max_ammo
```

## PROJECTILE TESTING PATTERNS
```python
def test_projectile_creation():
    proj = YourProjectile(100, 100, [1, 0], 20.0, 15, "owner")
    assert proj.location == [100, 100]
    assert proj.active

def test_projectile_movement():
    proj = YourProjectile(100, 100, [1, 0], 10.0, 15, "owner")
    initial_x = proj.location[0]
    proj.update(1/60)  # One frame
    assert proj.location[0] > initial_x

def test_projectile_custom_behavior():
    proj = YourProjectile(100, 100, [1, 0], 20.0, 15, "owner")
    initial_direction = proj.direction.copy()
    # Update multiple frames
    for _ in range(30):
        proj.update(1/60)
    # Verify custom behavior (direction change, etc.)
    assert proj.direction != initial_direction
```

## CHARACTER INTEGRATION
```python
def test_character_weapon_integration():
    char = Character("Test", "Test", "", [100, 100])
    weapon = YourWeapon()

    assert char.weapon is None
    weapon.pickup()
    char.weapon = weapon
    assert char.weapon is not None

    result = char.shoot([200, 100])
    assert result is not None
    assert weapon.ammo < weapon.max_ammo  # Ammo was consumed

def test_ammo_pickup_integration():
    from BASE_components.BASE_ammo import BaseAmmoPickup
    from GameFolder.arenas.GAME_arena import Arena
    
    arena = Arena(800, 600, headless=True)
    char = Character("Test", "Test", "", [100, 100])
    weapon = YourWeapon()
    
    # Give character weapon with low ammo
    weapon.ammo = 5
    weapon.pickup()
    char.weapon = weapon
    arena.add_character(char)
    
    # Place ammo pickup near character
    ammo = BaseAmmoPickup([105, 100], ammo_amount=10)
    arena.spawn_ammo(ammo)
    
    # Simulate collision
    arena.handle_collisions(0.016)
    
    # Character should have picked up ammo
    assert char.weapon.ammo == 15
    assert not ammo.is_active

def test_shield_damage_priority():
    """Test that shields absorb damage before health."""
    char = Character("Test", "Test", "", [100, 100])

    initial_health = char.health
    initial_shield = char.shield

    # Damage less than shield amount
    char.take_damage(20)
    assert char.shield == initial_shield - 20, f"Shield should absorb 20 damage, got {char.shield}"
    assert char.health == initial_health, f"Health should be unchanged, got {char.health}"

    # Damage exceeding remaining shield
    remaining_shield = char.shield
    excess_damage = 40
    char.take_damage(excess_damage)
    expected_health_loss = excess_damage - remaining_shield
    assert char.shield == 0, f"Shield should be depleted, got {char.shield}"
    assert char.health == initial_health - expected_health_loss, f"Health should lose {expected_health_loss}, got {char.health}"

def test_shield_regeneration():
    """Test shield regeneration mechanics."""
    char = Character("Test", "Test", "", [100, 100])
    import time

    # Deplete shield
    char.take_damage(50)
    assert char.shield == 0

    # Shield should not regen immediately
    char.update(0.5, [], 600)  # 0.5 seconds
    assert char.shield == 0, "Shield should not regen during damage delay"

    # Set last damage time to enable regen
    char.last_damage_time = time.time() - 2  # 2 seconds ago
    char.update(1.0, [], 600)  # 1 second update
    assert char.shield > 0, f"Shield should regenerate, got {char.shield}"
    assert char.shield <= char.max_shield, f"Shield should not exceed max, got {char.shield}"

def test_shield_network_serialization():
    """Test shield properties survive network serialization."""
    char = Character("Test", "Test", "", [100, 100])

    # Modify shield state
    char.take_damage(25)
    char.last_damage_time = 1234567890.0

    # Simulate network serialization/deserialization
    state = char.__getstate__()
    new_char = Character("Test2", "Test", "", [200, 200])
    new_char.__setstate__(state)

    # Verify shield properties were preserved
    assert new_char.shield == char.shield, f"Shield not preserved: {new_char.shield} != {char.shield}"
    assert new_char.max_shield == char.max_shield, f"Max shield not preserved: {new_char.max_shield} != {char.max_shield}"
    assert new_char.last_damage_time == char.last_damage_time, f"Last damage time not preserved: {new_char.last_damage_time} != {char.last_damage_time}"

def test_shield_ui_display():
    """Test shield visualization in UI."""
    from GameFolder.ui.GAME_ui import GameUI
    import pygame

    # Create mock screen for testing
    pygame.init()
    screen = pygame.Surface((1200, 700))

    ui = GameUI(screen, 1200, 700)
    char = Character("Test", "Test", "", [100, 100])

    # Test full shield display
    ui.draw_character_indicator(char, 1, [1000, 50])
    # Shield ring should be visible when shield > 0

    # Test depleted shield
    char.take_damage(50)  # Deplete shield
    ui.draw_character_indicator(char, 1, [1000, 50])
    # Shield ring should show as mostly gray/depleted

    pygame.quit()  # Clean up

def test_movement_with_obstacles():
    """Test movement respects collision boundaries."""
    arena = Arena(800, 600, headless=True)
    char = Character("Test", "Test", "", [100, 100])
    
    # Create obstacle with appropriate spacing
    obstacle = Platform(200, 400, 20, 200)
    arena.add_character(char)
    arena.platforms.append(obstacle)
    
    # Trigger movement ability
    initial_pos = char.location[0]
    char.move_action([1, 0], arena.platforms)
    
    # Verify collision was respected
    assert char.location[0] < obstacle.position, "Should be blocked by obstacle"
    
def test_ability_requires_alive_state():
    """Verify abilities can't be used when dead."""
    char = Character("Test", "Test", "", [100, 100])
    
    # Use proper method to change state
    char.die()
    assert char.is_alive is False
    
    # Ability should not activate
    result = char.use_ability([1, 0])
    assert result is False, "Dead character should not use abilities"
```

## NEW FEATURES TEST PATTERNS

**Character Size**: Test `char.width == 30` and `char.height == 30` after creation

**Invulnerability System**:
- Test `char.is_invulnerable == True` immediately after `char.respawn()` (not on `__init__`)
- Test damage is blocked when `is_invulnerable == True`
- Test invulnerability expires after 8.0 seconds via `char.update(delta_time)`

**Floor Platform**: Test characters cannot phase through floor (`plat.rect.y == arena_height`) but can phase through other platforms

**Ammo Scarcity**: Test `ammo_spawn_interval == 12.0`, ammo amounts `[5,10,15]`, max concurrent `2`

**Mirrored Ammo**: Test when ammo spawns at `[x,y]`, second pickup spawns at `[arena.width-x, y]` if valid platform exists

**Weapon Permanence**: Test dropped/death weapons don't respawn as pickups (`len(arena.weapon_pickups)` remains 0)

## RUNNING TESTS
```bash
python -m BASE_components.BASE_tests
```

## RULES
- [success] Function names: `test_*`
- [success] No parameters
- [success] Clear assertion messages
- [success] One concept per test
- [success] Import actual game classes from `GameFolder/`
- [error] No bare `assert` without messages

---

## [warning] CRITICAL: COMMON TEST PITFALLS

### 0. WRONG CONSTRUCTOR SIGNATURES (MOST COMMON!)
**Always check `__init__` parameters before creating objects in tests.**

```python
# [error] WRONG - Assumed separate velocity components
proj = MyProjectile(x, y, vx, vy, damage, owner_id)

# [success] CORRECT - Checked actual signature uses direction vector + speed
proj = MyProjectile(x, y, [1, 0], speed, damage, owner_id)
```

**Common mistakes:**
- Assuming `vx, vy` when implementation uses `direction, speed`
- Wrong parameter order
- Missing required parameters
- Wrong types (int vs float, list vs tuple)

### 0.5. WRONG RETURN TYPE ASSUMPTIONS
**Always check what methods actually return.**

```python
# [error] WRONG - Assumed shoot() returns list
projectiles = gun.shoot(x, y, tx, ty, owner_id)
assert len(projectiles) == 1  # FAILS if shoot() returns single object

# [success] CORRECT - Checked implementation
projectile = gun.shoot(x, y, tx, ty, owner_id)
assert isinstance(projectile, MyProjectile)

# [success] ALSO CORRECT - Handle both cases
result = gun.shoot(x, y, tx, ty, owner_id)
projectiles = result if isinstance(result, list) else [result] if result else []
```

### 0.75. WRONG ATTRIBUTE NAMES
**Never assume standard attribute names. Search for `self.` in the class.**

```python
# [error] WRONG - Assumed standard names
assert proj.vx > 0
assert proj.vy < 0
assert proj.is_on_floor

# [success] CORRECT - Found actual names in implementation
assert proj.horizontal_velocity > 0
assert proj.vertical_velocity < 0
assert proj.is_stationary
```

### 1. State Flags vs Computed Properties (CRITICAL!)
**Use proper methods to trigger state changes, not direct assignment.**

Some attributes like `is_alive` are state flags that are only updated by specific methods, not automatically computed from other values:

```python
# [error] WRONG - directly modifying underlying data
char.health = 0
assert char.is_alive is False  # FAILS! Flag not updated

# [success] CORRECT - use the proper method
char.die()  # Or use take_damage() which calls die()
assert char.is_alive is False  # PASSES
```

**General principle**: If a class has a method that changes state (like `die()`, `kill()`, `activate()`), use it instead of directly setting attributes. Direct assignment may skip important side effects and leave objects in invalid states.

### 1.5. Multi-Layer Systems
**Understand the order of operations in complex systems.**

Game systems often have multiple layers that process in sequence (e.g., shields → defense → health):

```python
# When testing layered systems, verify each layer's behavior
char.take_damage(amount)

# Test each layer independently:
# 1. First layer absorbs/modifies
# 2. Remaining passes to next layer
# 3. Final layer applies the result

# Check actual implementation for:
# - Processing order
# - Formulas and minimums
# - Side effects at each layer
```

### 2. Stateful Objects in Tests
**Objects that maintain state between method calls need fresh instances or explicit resets.**

```python
# [error] WRONG - state from first call affects second
obj = StatefulObject()
result1 = obj.action()  # Works
result2 = obj.action()  # Fails due to cooldown/state

# [success] CORRECT - fresh instance per test
def test_action():
    obj = StatefulObject()
    result = obj.action()

# [success] OR explicitly reset state
obj = StatefulObject()
obj.action()
obj.reset_state()  # or obj.internal_timer = 0
obj.action()  # Now works
```

**Common stateful systems**: Cooldowns, charges, ammo, animations, locks

### 3. Floating Point Precision in Loops
**Use integer iteration counts instead of floating point accumulation.**

```python
# [error] WRONG - float errors accumulate over iterations
dt = 0.1
total = 0.0
while total < target_time:
    obj.update(dt)
    total += dt  # Precision errors accumulate!

# [success] CORRECT - count iterations as integers
dt = 0.1
iterations = int(target_time / dt)
for i in range(iterations):
    obj.update(dt)
```

**Why**: Repeated floating point addition (`0.1 + 0.1 + 0.1...`) accumulates rounding errors, causing loops to end early/late.

### 4. Cumulative Effects in Simulation Loops
**Capture baseline state AFTER setup, BEFORE the action you're testing.**

```python
# [error] WRONG - setup loop affects baseline measurement
for _ in range(setup_frames):
    simulate()  # Effects accumulate
initial_state = capture_state()  # Already affected!
simulate()  # Test action
# Expected delta is wrong!

# [success] CORRECT - capture state between setup and test
for _ in range(setup_frames):
    simulate()
initial_state = capture_state()  # Capture AFTER setup
simulate()  # Single test action
assert state_changed_correctly(initial_state)
```

### 5. Object Scaling and Dimensions
**Use object's scale properties when calculating positions and sizes.**

```python
# [error] WRONG - ignores scaling
position = obj.location[0] + obj.width / 2

# [success] CORRECT - includes scale factor
position = obj.location[0] + (obj.width * obj.scale) / 2
```

### 6. Use Proper APIs
**Use designated methods instead of direct collection manipulation.**

```python
# [warning] RISKY - may skip initialization or validation
container.items = [item1, item2]

# [success] PREFERRED - uses proper API
container.add_item(item1)
container.add_item(item2)
```

### 7. Integer Truncation in Collision Systems
**Be aware of precision loss when systems use integer coordinates.**

```python
# [error] WRONG - assumes exact single-frame collision
obj = Object(pos=narrow_gap)
simulate_one_frame()
assert obj.collided  # FAILS! Precision loss prevents exact collision

# [success] CORRECT - allow multiple frames for collision to occur
obj = Object(pos=starting_position)
max_frames = 60
for _ in range(max_frames):
    simulate_one_frame()
    if obj.collided:
        break
assert obj.collided
```

**Principle**: When coordinates are converted between float and integer representations, precision is lost. Give enough space/time for collisions to be detected reliably.

### 8. Test Outcomes, Not Internal State
**Focus on observable behaviors and outcomes rather than exact internal values.**

```python
# [error] WRONG - brittle assertions on exact values
assert obj.position == 123.456
assert obj.internal_counter == 42

# [success] CORRECT - test meaningful outcomes
assert obj.reached_target
assert obj.direction_reversed
assert obj.damage > initial_damage
```

**Principle**: Internal state can vary due to timing, rounding, or implementation details. Test the outcomes that matter for game behavior.

### 9. Event-Driven Testing Pattern
**For time-based or collision-based events, use a loop-until-event pattern.**

```python
# [success] PATTERN: Simulate until event occurs or timeout
def test_collision_event():
    setup_objects()
    initial_state = capture_state()
    
    max_iterations = 100
    for i in range(max_iterations):
        simulate_step()
        if event_occurred():
            break
    
    assert event_occurred(), "Event should occur within timeout"
    assert state_changed_appropriately(initial_state)
```

**Use for**: Collisions, triggers, state transitions, time-based events

### 10. Coordinate System Awareness
The game uses TWO coordinate systems:
- **World coords**: Y=0 at bottom, Y increases upward (physics/game logic)
- **Screen coords**: Y=0 at top, Y increases downward (pygame/rendering)

**Principle**: Be explicit about which coordinate system you're using and ensure conversions use the correct dimensions.

```python
# Converting world to screen:
screen_y = arena.height - world_y - object_height

# [error] WRONG - mixing coordinate systems without conversion
# [success] CORRECT - explicit conversion with proper dimensions
```

### 10.5. Avoid Hardcoded Configuration Values
**Pass configuration as parameters or store during initialization.**

```python
# [error] WRONG - hardcoded value breaks tests with different configs
def process(self, data):
    max_size = 900  # Hardcoded!
    result = max_size - data.value
    
# [success] CORRECT - pass as parameter with sensible default
def process(self, data, max_size=900):
    result = max_size - data.value

# [success] ALSO CORRECT - store during initialization
def __init__(self, config):
    self.max_size = config.get('max_size', 900)
    
def process(self, data):
    result = self.max_size - data.value
```

**Why**: Tests often use different configurations (smaller arenas, different dimensions) to run faster or test edge cases. Hardcoded values cause coordinate mismatches and failed assertions.

### 11. Allow Margin for Precision Loss
**Start objects with sufficient separation to ensure reliable collision detection.**

```python
# [error] WRONG - minimal spacing affected by precision loss
obj1_pos = 200
obj2_pos = 201  # Only 1 unit apart

# [success] CORRECT - provide adequate margin
obj1_pos = 200
obj2_pos = 210  # Clear separation for reliable collision
```

**Principle**: Systems with precision loss (float→int conversion, coordinate transforms) need extra margin to ensure events are detected reliably.