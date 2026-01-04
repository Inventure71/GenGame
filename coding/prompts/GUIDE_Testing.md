# TESTING SYSTEM

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

def test_weapon_shooting():
    gun = YourWeapon()
    projectiles = gun.shoot(100, 100, 200, 100, "owner")
    assert isinstance(projectiles, list)
    assert len(projectiles) == expected_count
    assert all(p.damage == gun.damage for p in projectiles)

def test_weapon_cooldown():
    gun = YourWeapon()
    shot1 = gun.shoot(100, 100, 200, 100, "owner")
    shot2 = gun.shoot(100, 100, 200, 100, "owner")  # Immediate retry
    assert shot1 is not None
    assert shot2 is None  # Blocked by cooldown
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
```

## RUNNING TESTS
```bash
python -m BASE_components.BASE_tests
```

## RULES
- ✅ Function names: `test_*`
- ✅ No parameters
- ✅ Clear assertion messages
- ✅ One concept per test
- ✅ Import actual game classes from `GameFolder/`
- ❌ No bare `assert` without messages

---

## ⚠️ CRITICAL: COMMON TEST PITFALLS

### 1. Character Health Attribute
The Character class uses `health`, **NOT** `hp`:
```python
# ❌ WRONG - will cause AttributeError
initial_hp = target.hp
target.hp = 0

# ✅ CORRECT
initial_health = target.health
target.health = 0
```

The `is_alive` property checks `health > 0 AND lives > 0`. It's read-only.

### 2. Weapon Cooldown Between Shots
`weapon.shoot()` returns `None` if cooldown hasn't elapsed:
```python
# ❌ WRONG - second shot fails silently
gun = YourWeapon()
projs1 = gun.shoot(0, 0, 100, 100, "owner")  # Works
projs2 = gun.shoot(0, 0, 200, 200, "owner")  # Returns None!

# ✅ CORRECT - use new instance for each test
def test_shot_1():
    gun = YourWeapon()
    projs = gun.shoot(...)

def test_shot_2():
    gun = YourWeapon()  # Fresh instance, no cooldown
    projs = gun.shoot(...)

# ✅ OR reset cooldown manually
gun.last_shot_time = 0
```

### 3. Floating Point Timing Loops
Float accumulation causes precision errors:
```python
# ❌ WRONG - float errors accumulate
dt = 0.1
total_time = 0.0
while total_time < 1.15:  # charge_duration - 0.05
    proj.update(dt)
    total_time += dt  # 0.1 + 0.1 + ... != exact sum!

# ✅ CORRECT - use integer frame counting
dt = 0.1
frames_needed = int(1.2 / dt)  # charge_duration / dt
for i in range(frames_needed):
    proj.update(dt)
    if i < frames_needed - 1:
        assert proj.state == 'CHARGING'
```

### 4. Cumulative Effects in Arena Loops
`arena.handle_collisions(dt)` applies ALL effects each call:
```python
# ❌ WRONG - recoil applied 15 times!
for _ in range(15):
    arena.handle_collisions(0.1)  # Each call applies recoil
initial_loc = list(char.location)  # Already moved!
arena.handle_collisions(0.1)
# Expected 25 units, but char already moved 375 units

# ✅ CORRECT - track state AFTER setup loop, BEFORE test action
for _ in range(15):
    arena.handle_collisions(0.1)
initial_loc = list(char.location)  # Capture AFTER loop
arena.handle_collisions(0.1)       # Single test action
expected_recoil = 25.0
assert abs(char.location[0] - (initial_loc[0] - expected_recoil)) < 0.1
```

### 5. Character Scale Ratio
Character dimensions use `scale_ratio` (default 1.0):
```python
# ✅ CORRECT - always use scale_ratio
char_center_x = char.location[0] + (char.width * char.scale_ratio) / 2
char_center_y = char.location[1] + (char.height * char.scale_ratio) / 2
```

### 6. Arena Character Management
Use proper methods, not direct assignment:
```python
# ⚠️ RISKY - may skip initialization
arena.characters = [char1, char2]

# ✅ PREFERRED - uses proper initialization
arena.add_character(char1)
arena.add_character(char2)
```

### 7. pygame.Rect Integer Truncation (CRITICAL!)
**pygame.Rect only stores integers!** Float positions get truncated, causing collision detection failures.

```python
# ❌ WRONG - relies on exact single-frame collision
disc = DiscProjectile(200, 201, [0, -1], 100.0, 25.0, "owner")  # Just 1 pixel above platform
arena.handle_collisions(1/60)  # Moves ~1.67 pixels
assert disc.bounces == 1  # FAILS! Rect truncation causes touch, not overlap

# ✅ CORRECT - run multiple frames until behavior occurs
disc = DiscProjectile(200, 210, [0, -1], 100.0, 25.0, "owner")  # Start further away
for _ in range(20):  # Allow enough frames
    arena.handle_collisions(1/60)
    if disc.bounces > 0:
        break
assert disc.bounces == 1  # PASSES - collision eventually detected
```

**Why this happens**: When converting world coords to screen coords, floats like `380.67` become `380`. If a rect ends at exactly `400` and another starts at `400`, they TOUCH but don't OVERLAP. `colliderect()` returns False for touching rects.

### 8. Test Behaviors, Not Exact Positions
Position assertions are fragile due to coordinate conversion and truncation. Test the BEHAVIOR instead:

```python
# ❌ WRONG - fragile position assertion
assert disc.location[1] == pytest.approx(200)  # May fail due to correction logic

# ✅ CORRECT - test the behavior that matters
assert disc.bounces == 1                        # Bounce happened
assert disc.direction[1] > 0                    # Direction reversed (going up)
assert disc.damage > initial_damage             # Stats increased
assert disc.speed > initial_speed               # Speed boosted
```

### 9. Collision Testing Best Practices
For ANY collision-based test (bouncing, damage, pickup):

```python
# ✅ PATTERN: Loop until behavior OR max iterations
def test_projectile_collision():
    arena = Arena(800, 600)
    proj = MyProjectile(x, y, direction, speed, damage, "owner")
    arena.projectiles.append(proj)
    
    initial_state = capture_relevant_state(proj)
    
    # Run frames until collision OR timeout
    max_frames = 60  # ~1 second at 60fps
    for frame in range(max_frames):
        arena.handle_collisions(1/60)
        if collision_occurred(proj):  # e.g., proj.bounces > 0, not proj.active, etc.
            break
    
    # Assert on BEHAVIOR, not exact position
    assert collision_occurred(proj), f"Collision should occur within {max_frames} frames"
    assert_behavior_changed(proj, initial_state)
```

### 10. Coordinate System Awareness
The game uses TWO coordinate systems:
- **World coords**: Y=0 at bottom, Y increases upward (physics/game logic)
- **Screen coords**: Y=0 at top, Y increases downward (pygame/rendering)

```python
# Converting world to screen for collision checks:
screen_y = arena.height - world_y - object_height

# ❌ WRONG - mixing coordinate systems
plat = Platform(100, 200, ...)  # This is SCREEN coords!
disc_world_y = 200              # This is WORLD coords!
# These are NOT at the same position!

# ✅ CORRECT - be explicit about coordinate system
# Platform at screen (100, 400) = world-y top at 600-400 = 200
plat = Platform(100, 400, 200, 20)  # Screen coords
disc = DiscProjectile(200, 210, ...)  # World coords, above platform top (200)
```

### 11. Give Entities Room to Move
Start entities far enough apart that integer truncation doesn't matter:

```python
# ❌ WRONG - positions too close, truncation breaks collision
proj_y = 201   # 1 pixel above platform at 200
# After 1 frame: 199.33 → screen rect ends at 400
# Platform rect starts at 400 → TOUCH, no overlap!

# ✅ CORRECT - give 5-10+ pixels margin
proj_y = 210   # 10 pixels above platform
# After several frames, will clearly overlap
```