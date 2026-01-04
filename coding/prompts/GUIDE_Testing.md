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