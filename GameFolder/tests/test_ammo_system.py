"""
Tests for the ammo system.
Verifies ammo consumption, pickups, and persistence.
"""

from GameFolder.characters.GAME_character import Character
from GameFolder.weapons.GAME_weapon import Weapon
from GameFolder.arenas.GAME_arena import Arena
from BASE_components.BASE_ammo import BaseAmmoPickup


def test_weapon_starts_with_full_ammo():
    """Weapons should start with full ammo."""
    weapon = Weapon("Test Gun", damage=10, cooldown=0.5, projectile_speed=20.0, max_ammo=30)
    assert weapon.ammo == weapon.max_ammo
    assert weapon.ammo == 30


def test_shooting_consumes_ammo():
    """Each shot should consume ammo."""
    weapon = Weapon("Test Gun", damage=10, cooldown=0.5, projectile_speed=20.0, max_ammo=30, ammo_per_shot=1)
    initial_ammo = weapon.ammo
    
    projectile = weapon.shoot(100, 100, 200, 100, "owner_id")
    
    assert projectile is not None
    assert weapon.ammo == initial_ammo - 1
    assert weapon.ammo == 29


def test_cannot_shoot_without_ammo():
    """Weapon should not shoot when out of ammo."""
    weapon = Weapon("Test Gun", damage=10, cooldown=0.5, projectile_speed=20.0, max_ammo=5, ammo_per_shot=1)
    
    # Shoot until empty
    for _ in range(5):
        weapon.shoot(100, 100, 200, 100, "owner_id")
        weapon.last_shot_time = 0  # Reset cooldown
    
    assert weapon.ammo == 0
    
    # Try to shoot when empty
    result = weapon.shoot(100, 100, 200, 100, "owner_id")
    assert result is None


def test_add_ammo_increases_count():
    """Adding ammo should increase ammo count."""
    weapon = Weapon("Test Gun", damage=10, cooldown=0.5, projectile_speed=20.0, max_ammo=30, ammo_per_shot=1)
    weapon.ammo = 10
    
    weapon.add_ammo(5)
    assert weapon.ammo == 15


def test_add_ammo_caps_at_max():
    """Adding ammo should not exceed max_ammo."""
    weapon = Weapon("Test Gun", damage=10, cooldown=0.5, projectile_speed=20.0, max_ammo=30, ammo_per_shot=1)
    weapon.ammo = 25
    
    weapon.add_ammo(100)
    assert weapon.ammo == 30


def test_reload_refills_ammo():
    """Reload should restore ammo to max."""
    weapon = Weapon("Test Gun", damage=10, cooldown=0.5, projectile_speed=20.0, max_ammo=30, ammo_per_shot=1)
    weapon.ammo = 5
    
    weapon.reload()
    assert weapon.ammo == weapon.max_ammo


def test_ammo_persists_when_dropped():
    """Ammo should persist when weapon is dropped."""
    weapon = Weapon("Test Gun", damage=10, cooldown=0.5, projectile_speed=20.0, max_ammo=30, ammo_per_shot=1)
    
    # Shoot a few times
    for _ in range(5):
        weapon.shoot(100, 100, 200, 100, "owner_id")
        weapon.last_shot_time = 0
    
    remaining_ammo = weapon.ammo
    assert remaining_ammo == 25
    
    # Drop weapon
    weapon.drop([200, 200])
    
    # Ammo should be unchanged
    assert weapon.ammo == remaining_ammo


def test_ammo_pickup_creation():
    """Ammo pickup should be created correctly."""
    ammo = BaseAmmoPickup([300, 200], ammo_amount=15)
    
    assert ammo.location == [300, 200]
    assert ammo.ammo_amount == 15
    assert ammo.is_active


def test_ammo_pickup_collection():
    """Character should collect ammo when walking over it."""
    arena = Arena(800, 600, headless=True)
    char = Character("Test", "Test", "", [100, 100])
    weapon = Weapon("Test Gun", damage=10, cooldown=0.5, projectile_speed=20.0, max_ammo=30, ammo_per_shot=1)
    
    # Give character weapon with low ammo
    weapon.ammo = 10
    weapon.pickup()
    char.weapon = weapon
    arena.add_character(char)
    
    # Place ammo pickup at character's location
    ammo = BaseAmmoPickup([char.location[0], char.location[1]], ammo_amount=10)
    arena.spawn_ammo(ammo)
    
    # Trigger collision detection
    for _ in range(5):
        arena.handle_collisions(0.016)
        if not ammo.is_active:
            break
    
    # Character should have picked up ammo
    assert char.weapon.ammo == 20
    assert not ammo.is_active


def test_character_without_weapon_cannot_pickup_ammo():
    """Character without weapon should not collect ammo."""
    arena = Arena(800, 600, headless=True)
    char = Character("Test", "Test", "", [100, 100])
    arena.add_character(char)
    
    # Character has no weapon
    assert char.weapon is None
    
    # Place ammo pickup
    ammo = BaseAmmoPickup([char.location[0], char.location[1]], ammo_amount=10)
    arena.spawn_ammo(ammo)
    
    # Trigger collision detection
    arena.handle_collisions(0.016)
    
    # Ammo should still be active (not collected)
    assert ammo.is_active


def test_ammo_spawns_automatically():
    """Arena should spawn ammo pickups automatically."""
    arena = Arena(800, 600, headless=True)
    
    # Add a platform for spawning
    from GameFolder.platforms.GAME_platform import Platform
    arena.add_platform(Platform(100, 400, 200, 20))
    
    initial_ammo_count = len(arena.ammo_pickups)
    
    # Simulate time passing to trigger ammo spawn
    for _ in range(100):
        arena.manage_ammo_spawns(0.1)  # 10 seconds total
    
    # Should have spawned ammo
    assert len(arena.ammo_pickups) > initial_ammo_count


def test_weapon_with_custom_ammo_per_shot():
    """Weapons can consume multiple ammo per shot."""
    weapon = Weapon("Heavy Gun", damage=50, cooldown=2.0, projectile_speed=30.0, max_ammo=20, ammo_per_shot=3)
    
    initial_ammo = weapon.ammo
    weapon.shoot(100, 100, 200, 100, "owner_id")
    
    assert weapon.ammo == initial_ammo - 3

