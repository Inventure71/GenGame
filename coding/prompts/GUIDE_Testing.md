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

### 1.5. Shield Damage Priority (CRITICAL!)
**Shields absorb damage BEFORE health!** All damage calculations must account for shield absorption:
```python
# ❌ WRONG - ignores shield absorption
char.take_damage(30)
assert char.health == initial_health - 30  # FAILS! Shield absorbs first

# ✅ CORRECT - account for shield priority
damage = 30
shield_absorbed = min(damage, char.shield)
health_damage = max(0, damage - char.shield)
char.take_damage(damage)
assert char.shield == initial_shield - shield_absorbed
assert char.health == initial_health - health_damage
```

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
    arena = Arena(800, 600, headless=True)
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