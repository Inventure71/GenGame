"""
Tests for Flight Mechanic and Singularity Cannon.
"""
import time
import math
from GameFolder.characters.GAME_character import Character
from GameFolder.weapons.BlackHoleGun import BlackHoleGun
from GameFolder.projectiles.BlackHoleProjectile import BlackHoleProjectile
from GameFolder.arenas.GAME_arena import Arena
from GameFolder.platforms.GAME_platform import Platform

def test_flight_mechanic_initial_state():
    """Verify character starts with full flight time."""
    char = Character("Test", "Test", "", [100, 100])
    assert char.flight_time_remaining == char.max_flight_time, "Should start with full flight time"
    assert not char.needs_recharge, "Should not need recharge initially"
    assert not char.is_currently_flying, "Should not be flying initially"

def test_flight_consumption():
    """Verify flight time decreases when flying."""
    char = Character("Test", "Test", "", [100, 100])
    char.on_ground = False
    # Move up to trigger flight
    char.move([0, 1]) 
    
    assert char.is_currently_flying, "Should be flying after upward movement in air"
    
    delta = 0.5
    char.update(delta)
    
    expected = char.max_flight_time - delta
    assert abs(char.flight_time_remaining - expected) < 0.001, f"Flight time should decrease by {delta}"

def test_flight_depletion():
    """Verify character stops flying when fuel is empty."""
    char = Character("Test", "Test", "", [100, 100])
    char.on_ground = False
    char.move([0, 1])
    
    # Deplete flight time
    char.update(char.max_flight_time + 0.1)
    
    assert char.flight_time_remaining == 0, "Flight time should be 0"
    assert char.needs_recharge, "Should need recharge after depletion"
    assert not char.is_currently_flying, "Should stop flying after depletion"
    assert not char.can_fly, "Should not be able to fly until recharged"

def test_flight_recharge():
    """Verify flight time recharges on ground."""
    char = Character("Test", "Test", "", [100, 100])
    char.on_ground = False
    char.move([0, 1])
    char.update(1.0) # Use 1s
    
    initial_remaining = char.flight_time_remaining
    
    # Land
    char.on_ground = True
    char.update(0.5)
    
    assert char.flight_time_remaining > initial_remaining, "Flight time should recharge on ground"
    
    # Full recharge
    char.update(5.0)
    assert char.flight_time_remaining == char.max_flight_time, "Should fully recharge"
    assert not char.needs_recharge, "needs_recharge should be False after full recharge"

def test_black_hole_gun_creation():
    """Verify Singularity Cannon properties."""
    gun = BlackHoleGun()
    assert gun.name == "Singularity Cannon"
    assert gun.cooldown == 6.0
    assert gun.damage == 0.5

def test_black_hole_shooting():
    """Verify shooting creates a BlackHoleProjectile."""
    gun = BlackHoleGun()
    # Reset cooldown manually if needed, but it should be 0 initially
    projs = gun.shoot(100, 100, 200, 200, "player1")
    
    assert len(projs) == 1, "Should create 1 projectile"
    assert isinstance(projs[0], BlackHoleProjectile), "Should be a BlackHoleProjectile"
    assert projs[0].target_pos == (200, 200), "Target position should match"

def test_black_hole_movement():
    """Verify projectile moves to target then stops."""
    proj = BlackHoleProjectile(100, 100, 200, 100, "player1")
    assert not proj.is_stationary
    
    # Update 1 frame
    proj.update(0.1) 
    assert proj.location[0] > 100, "Projectile should move towards target"
    
    # Teleport near target and update
    proj.location = [195, 100]
    proj.update(0.1)
    assert proj.is_stationary, "Should become stationary near target"
    assert list(proj.location) == [200, 100], "Should snap to target location"

def test_black_hole_duration():
    """Verify projectile disappears after duration."""
    proj = BlackHoleProjectile(100, 100, 100, 100, "player1")
    proj.is_stationary = True
    
    proj.update(proj.duration - 0.1)
    assert proj.active, "Should be active before duration ends"
    
    proj.update(0.2)
    assert not proj.active, "Should be inactive after duration"

def test_black_hole_gravity_pull():
    """Verify Arena logic pulls characters towards the black hole."""
    arena = Arena(800, 600)
    char = Character("Victim", "Desc", "", [100, 100])
    arena.characters.append(char)
    
    proj = BlackHoleProjectile(200, 100, 200, 100, "attacker")
    proj.is_stationary = True
    arena.projectiles.append(proj)
    
    # Initial distance is 100
    initial_x = char.location[0]
    
    # Run collision logic
    arena.handle_collisions(0.016)
    
    assert char.location[0] > initial_x, "Character should be pulled towards the black hole"
    assert char.location[0] <= 200, "Character should not overshoot significantly"

def test_black_hole_damage():
    """Verify black hole deals damage when close."""
    arena = Arena(800, 600)
    # Spawn character directly on top of black hole
    char = Character("Victim", "Desc", "", [200, 100])
    char.health = 100
    arena.characters.append(char)
    
    proj = BlackHoleProjectile(200, 100, 200, 100, "attacker")
    proj.is_stationary = True
    arena.projectiles.append(proj)
    
    # Run collision logic
    delta = 0.5
    arena.handle_collisions(delta)
    
    assert char.health < 100, "Character should take damage when inside the black hole"

def test_lootpool_registration():
    """Verify BlackHoleGun is in the lootpool."""
    arena = Arena()
    assert "BlackHoleGun" in arena.lootpool, "BlackHoleGun was not registered in the lootpool"
    
    gun_class = arena.lootpool["BlackHoleGun"]
    assert gun_class == BlackHoleGun, "Lootpool should point to BlackHoleGun class"