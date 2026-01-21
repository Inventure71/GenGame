"""
Basic functionality tests for core game systems.
Tests character creation, movement, weapon pickup, and basic combat.
Uses Pistol as the basic weapon for all weapon-related tests.
"""

import pygame
from GameFolder.arenas.GAME_arena import Arena
from GameFolder.characters.GAME_character import Character
from GameFolder.weapons.Pistol import Pistol
from GameFolder.weapons.GAME_weapon import Weapon
from GameFolder.projectiles.GAME_projectile import Projectile
from GameFolder.platforms.GAME_platform import Platform
from GameFolder.setup import setup_battle_arena


def test_character_creation():
    """Test that a character can be created with basic properties."""
    char = Character("TestPlayer", "Test Description", "", [100.0, 200.0], width=30, height=30)
    
    assert char.name == "TestPlayer", "Character name should be set correctly"
    assert char.location == [100.0, 200.0], "Character location should be set correctly"
    assert char.width == 30, "Character width should be set correctly"
    assert char.height == 30, "Character height should be set correctly"
    assert char.health == 100.0, "Character should start with 100 health"
    assert char.max_health == 100.0, "Character max health should be 100"
    assert char.lives == 3, "Character should start with 3 lives"
    assert char.is_alive is True, "Character should be alive initially"
    assert char.is_eliminated is False, "Character should not be eliminated initially"


def test_character_horizontal_movement():
    """Test that a character can move horizontally."""
    arena = Arena(800, 600, headless=True)
    char = Character("TestPlayer", "", "", [100.0, 100.0])
    arena.add_character(char)
    
    initial_x = char.location[0]
    
    # Move right
    char.move([1, 0], arena.platforms)
    assert char.location[0] > initial_x, "Character should move right"
    
    # Move left
    new_x = char.location[0]
    char.move([-1, 0], arena.platforms)
    assert char.location[0] < new_x, "Character should move left"


def test_character_jumping():
    """Test that a character can jump."""
    arena = Arena(800, 600, headless=True)
    platform = Platform(100, 500, 200, 20)  # Platform at screen y=500
    arena.add_platform(platform)
    
    # Place character on platform (world y = 600 - 500 - 20 = 80)
    char = Character("TestPlayer", "", "", [200.0, 80.0])
    char.on_ground = True
    arena.add_character(char)
    
    initial_y = char.location[1]
    initial_velocity = char.vertical_velocity
    
    # Jump
    char.jump()
    
    assert char.vertical_velocity > initial_velocity, "Jump should increase vertical velocity"
    assert char.vertical_velocity > 0, "Vertical velocity should be positive after jump"


def test_character_gravity():
    """Test that a character falls due to gravity."""
    arena = Arena(800, 600, headless=True)
    char = Character("TestPlayer", "", "", [100.0, 500.0])
    arena.add_character(char)
    
    initial_y = char.location[1]
    
    # Apply gravity multiple times to see the effect
    # First call sets velocity negative, second call moves character
    char.apply_gravity(arena.height, arena.platforms, arena.width)
    char.apply_gravity(arena.height, arena.platforms, arena.width)
    
    # Character should fall (y decreases in world coordinates)
    assert char.location[1] < initial_y, "Character should fall due to gravity"
    assert char.vertical_velocity < 0, "Vertical velocity should be negative (falling)"


def test_character_shield_system():
    """Test that character shield absorbs damage before health."""
    arena = Arena(800, 600, headless=True)
    char = Character("TestPlayer", "", "", [100.0, 100.0])
    arena.add_character(char)
    
    initial_health = char.health
    initial_shield = char.shield
    
    # Take damage less than shield
    char.take_damage(20.0)
    
    assert char.shield < initial_shield, "Shield should decrease"
    assert char.health == initial_health, "Health should not decrease when shield absorbs damage"
    
    # Take more damage than shield
    char.take_damage(60.0)
    
    assert char.shield == 0.0, "Shield should be depleted"
    assert char.health < initial_health, "Health should decrease after shield is gone"


def test_pistol_creation():
    """Test that a Pistol weapon can be created with correct properties."""
    pistol = Pistol()
    
    assert pistol.name == "Pistol", "Pistol name should be 'Pistol'"
    assert pistol.damage == 10, "Pistol damage should be 10"
    assert pistol.cooldown == 0.3, "Pistol cooldown should be 0.3"
    assert pistol.projectile_speed == 15, "Pistol projectile speed should be 15"
    assert pistol.max_ammo == 30, "Pistol max ammo should be 30"
    assert pistol.ammo == 30, "Pistol should start with full ammo"
    assert pistol.is_equipped is False, "Pistol should start unequipped"


def test_pistol_shooting():
    """Test that Pistol can shoot projectiles."""
    pistol = Pistol()
    owner_id = "test_owner"
    
    # Shoot
    proj = pistol.shoot(100.0, 100.0, 200.0, 100.0, owner_id)
    
    assert proj is not None, "Pistol should return a projectile"
    assert isinstance(proj, Projectile), "Pistol should shoot a Projectile"
    assert proj.owner_id == owner_id, "Projectile owner_id should match"
    assert proj.damage == 10, "Projectile damage should match weapon damage"
    assert proj.active is True, "Projectile should be active on spawn"
    assert pistol.ammo == 29, "Ammo should decrease after shooting"


def test_pistol_cooldown():
    """Test that Pistol enforces cooldown between shots."""
    pistol = Pistol()
    owner_id = "test_owner"
    
    # First shot
    proj1 = pistol.shoot(100.0, 100.0, 200.0, 100.0, owner_id)
    assert proj1 is not None, "First shot should succeed"
    
    # Immediate second shot (should fail due to cooldown)
    proj2 = pistol.shoot(100.0, 100.0, 200.0, 100.0, owner_id)
    assert proj2 is None, "Second shot should be blocked by cooldown"


def test_weapon_pickup():
    """Test that a character can pick up a weapon."""
    arena = Arena(800, 600, headless=True)
    char = Character("TestPlayer", "", "", [100.0, 100.0])
    pistol = Pistol([100.0, 100.0])
    arena.add_character(char)
    arena.spawn_weapon(pistol)
    
    assert char.weapon is None, "Character should start without weapon"
    assert pistol.is_equipped is False, "Weapon should start unequipped"
    
    # Trigger pickup (character at same location as weapon)
    arena.handle_collisions(0.016)
    
    assert char.weapon is not None, "Character should have weapon after pickup"
    assert pistol.is_equipped is True, "Weapon should be equipped after pickup"


def test_character_shooting_with_weapon():
    """Test that a character can shoot using their weapon."""
    arena = Arena(800, 600, headless=True)
    char = Character("TestPlayer", "", "", [100.0, 100.0])
    pistol = Pistol()
    char.weapon = pistol
    pistol.pickup()
    arena.add_character(char)
    
    initial_ammo = pistol.ammo
    
    # Character shoots
    projs = char.shoot([200.0, 100.0])
    
    assert projs is not None, "Character should shoot projectiles"
    assert pistol.ammo < initial_ammo, "Weapon ammo should decrease after shooting"
    
    # Add projectile to arena
    if isinstance(projs, list):
        arena.projectiles.extend(projs)
    else:
        arena.projectiles.append(projs)
    
    assert len(arena.projectiles) > 0, "Arena should have projectiles after shooting"


def test_projectile_movement():
    """Test that projectiles move correctly."""
    arena = Arena(800, 600, headless=True)
    proj = Projectile(100.0, 100.0, [1.0, 0.0], 20.0, 10.0, "owner")
    arena.projectiles.append(proj)
    
    initial_x = proj.location[0]
    
    # Update projectile
    proj.update(0.016)
    arena.handle_collisions(0.016)
    
    assert proj.location[0] > initial_x, "Projectile should move in direction"
    assert proj.active is True, "Projectile should remain active"


def test_projectile_collision_with_character():
    """Test that projectiles damage characters on collision."""
    arena = Arena(800, 600, headless=True)
    attacker = Character("Attacker", "", "", [100.0, 100.0])
    attacker.id = "attacker"
    victim = Character("Victim", "", "", [200.0, 100.0])
    victim.id = "victim"
    # Deplete victim's shield so we can see health damage
    victim.shield = 0
    arena.add_character(attacker)
    arena.add_character(victim)
    
    initial_health = victim.health
    
    # Create projectile from attacker targeting victim
    # Position projectile at victim's location for collision
    proj = Projectile(victim.location[0], victim.location[1], 
                      [1.0, 0.0], 20.0, 10.0, attacker.id)
    arena.projectiles.append(proj)
    
    # Handle collision
    arena.handle_collisions(0.016)
    
    assert victim.health < initial_health, "Victim should take damage from projectile"
    assert proj.active is False, "Projectile should be deactivated after hit"


def test_arena_setup():
    """Test that setup_battle_arena creates a valid arena."""
    arena = setup_battle_arena(headless=True, player_names=["Player1", "Player2"])
    
    assert arena is not None, "Arena should be created"
    assert arena.width == 1400, "Arena width should be 1400"
    assert arena.height == 900, "Arena height should be 900"
    assert len(arena.characters) == 2, "Arena should have 2 characters"
    assert len(arena.platforms) > 0, "Arena should have platforms"
    assert "Pistol" in arena.lootpool, "Pistol should be in lootpool"


def test_character_death():
    """Test that a character dies when health reaches zero."""
    arena = Arena(800, 600, headless=True)
    char = Character("TestPlayer", "", "", [100.0, 100.0])
    arena.add_character(char)
    
    assert char.is_alive is True, "Character should be alive initially"
    
    # Character has 50 shield + 100 health, defense reduces by 5
    # To kill: need to break shield (50) + kill health (100 + 5 defense = 105)
    # Total: 155 damage minimum
    char.take_damage(155.0)
    
    assert char.health <= 0, "Character health should be <= 0"
    assert char.is_alive is False, "Character should be dead"


def test_character_respawn():
    """Test that a character respawns after death."""
    arena = Arena(800, 600, headless=True)
    char = Character("TestPlayer", "", "", [100.0, 100.0])
    char.spawn_location = [100.0, 100.0]
    arena.add_character(char)
    
    # Kill character (50 shield + 100 health + 5 defense = 155 minimum)
    char.take_damage(155.0)
    assert char.is_alive is False, "Character should be dead"
    
    # Respawn
    char.respawn()
    
    assert char.is_alive is True, "Character should be alive after respawn"
    assert char.health == char.max_health, "Character should have full health after respawn"
    assert char.location == char.spawn_location, "Character should respawn at spawn location"


def test_weapon_ammo_depletion():
    """Test that weapon cannot shoot when out of ammo."""
    pistol = Pistol()
    owner_id = "test_owner"
    
    # Shoot until empty
    for _ in range(30):
        pistol.shoot(100.0, 100.0, 200.0, 100.0, owner_id)
        pistol.last_shot_time = 0  # Reset cooldown
    
    assert pistol.ammo == 0, "Pistol should be out of ammo"
    
    # Try to shoot when empty
    result = pistol.shoot(100.0, 100.0, 200.0, 100.0, owner_id)
    assert result is None, "Pistol should not shoot when out of ammo"


def test_platform_collision():
    """Test that characters can land on platforms."""
    arena = Arena(800, 600, headless=True)
    # Platform at screen y=500, so world y = 600 - 500 - 20 = 80
    platform = Platform(100, 500, 200, 20)
    arena.add_platform(platform)
    
    # Character above platform, falling
    # Position character so feet are just above platform (world y slightly above 80)
    # Character height is 50 by default, so position at world y = 80 + 50 = 130
    char = Character("TestPlayer", "", "", [200.0, 130.0])
    char.vertical_velocity = -10.0  # Falling
    arena.add_character(char)
    
    # Apply gravity multiple times to allow character to fall and land
    for _ in range(10):
        char.apply_gravity(arena.height, arena.platforms, arena.width)
        if char.on_ground:
            break
    
    # Character should land on platform
    assert char.on_ground is True, "Character should be on ground after landing on platform"
    assert char.vertical_velocity == 0, "Vertical velocity should be zero when on ground"
