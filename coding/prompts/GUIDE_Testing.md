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