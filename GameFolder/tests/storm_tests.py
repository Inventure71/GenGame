"""
Tests for StormBringer weapon and StormCloud projectile.
"""

import math
import pygame
from GameFolder.weapons.GAME_weapon import StormBringer
from GameFolder.projectiles.GAME_projectile import StormCloud
from GameFolder.arenas.GAME_arena import Arena
from GameFolder.characters.GAME_character import Character
from GameFolder.setup import setup_battle_arena

def test_storm_bringer_properties():
    """Verify StormBringer initial properties."""
    gun = StormBringer()
    assert gun.name == "Storm Bringer"
    assert gun.damage == 0.2
    assert gun.cooldown == 3.0

def test_storm_bringer_shooting():
    """Verify StormBringer spawns a StormCloud."""
    gun = StormBringer()
    gun.last_shot_time = 0 
    projectiles = gun.shoot(100, 100, 200, 100, "player1")
    assert len(projectiles) == 1
    assert isinstance(projectiles[0], StormCloud)
    assert projectiles[0].target_pos == [200, 100]

def test_storm_cloud_movement():
    """Verify StormCloud moves towards target then starts raining."""
    # Start at 100, target 200. Speed 5.
    cloud = StormCloud(100, 100, [200, 100], "player1")
    assert not cloud.is_raining
    
    # Move partway
    cloud.update(0.1) 
    # dist moved = 5 * (0.1 * 60) = 30
    assert 129 < cloud.location[0] < 131, f"Expected x ~130, got {cloud.location[0]}"
    assert not cloud.is_raining
    
    # Move to target
    cloud.update(1.0)
    assert cloud.is_raining, "Cloud should be raining after reaching target"
    assert abs(cloud.location[0] - 200) < 6, "Cloud should be at or near target"

def test_storm_cloud_damage_and_slow():
    """Verify StormCloud deals damage and slows characters in the Arena."""
    arena = Arena(800, 600)
    # Cloud at (200, 400). It's raining.
    cloud = StormCloud(200, 400, [200, 400], "attacker")
    cloud.is_raining = True
    arena.projectiles.append(cloud)
    
    # Character under the cloud (World-Y 300 is below 400)
    char = Character("Victim", "Desc", "", [210, 300])
    char.id = "victim"
    # Deplete shields first so we can test health damage
    char.shield = 0
    arena.characters.append(char)

    # Pre-checks
    assert char.speed_multiplier == 1.0
    initial_health = char.health
    
    # Update arena. StormCloud damage in Arena is (damage * 40) with 10% chance.
    # Let's run it many times to ensure we hit the 10% chance eventually or just check slow.
    for _ in range(100):
        arena.handle_collisions(0.1)
    
    assert char.speed_multiplier == 0.4, "Character should be slowed by StormCloud"
    assert char.health < initial_health, "Character should eventually take damage from StormCloud"

def test_storm_cloud_duration():
    """Verify StormCloud deactivates after rain duration."""
    cloud = StormCloud(100, 100, [100, 100], "player1")
    cloud.is_raining = True
    cloud.rain_timer = 0
    
    cloud.update(cloud.rain_duration - 0.1)
    assert cloud.active
    
    cloud.update(0.2)
    assert not cloud.active, "Cloud should deactivate after duration"

def test_storm_multiplier_recovery():
    """Verify character recovers from speed slow over time."""
    char = Character("Tester", "Desc", "", [100, 100])
    char.speed_multiplier = 0.4
    
    char.update(0.5)
    assert char.speed_multiplier > 0.4, "Multiplier should start recovering"
    
    char.update(2.0)
    assert char.speed_multiplier == 1.0, "Multiplier should fully recover to 1.0"

def test_jump_multiplier_recovery():
    """Verify character recovers from jump height reduction over time."""
    char = Character("Tester", "Desc", "", [100, 100])
    char.jump_height_multiplier = 0.5
    
    char.update(1.0)
    assert char.jump_height_multiplier > 0.5, "Jump multiplier should recover"
    assert char.jump_height_multiplier == 1.0, "Jump multiplier should be 1.0 after 1s recovery (0.5 + 0.5*1.0)"