"""
Tests for Ricochet Disc Launcher weapon and its associated projectiles.
"""

import pytest
import pygame
import math
from GameFolder.weapons.RicochetLauncher import RicochetLauncher
from GameFolder.projectiles.RicochetProjectiles import DiscProjectile, DiscShard
from GameFolder.arenas.GAME_arena import Arena
from GameFolder.characters.GAME_character import Character
from GameFolder.platforms.GAME_platform import Platform
from GameFolder.setup import setup_battle_arena

def test_ricochet_launcher_properties():
    """Verify Ricochet Launcher initial properties."""
    launcher = RicochetLauncher()
    assert launcher.name == "Ricochet Disc Launcher"
    assert launcher.damage == 25.0
    assert launcher.cooldown == 0.6
    assert launcher.projectile_speed == 25.0

def test_ricochet_launcher_shooting():
    """Verify Ricochet Launcher spawns a DiscProjectile."""
    launcher = RicochetLauncher()
    launcher.last_shot_time = 0
    # Shoot from (100, 100) towards (200, 100) - straight right
    projectiles = launcher.shoot(100, 100, 200, 100, "player1")
    assert len(projectiles) == 1
    assert isinstance(projectiles[0], DiscProjectile)
    assert projectiles[0].owner_id == "player1"
    assert projectiles[0].direction == [1.0, 0.0]
    assert projectiles[0].speed == 25.0
    assert projectiles[0].width == 20
    assert projectiles[0].height == 20

def test_disc_projectile_initial_state():
    """Verify DiscProjectile initial state and attributes."""
    disc = DiscProjectile(100, 100, [1, 0], 25.0, 25.0, "owner")
    assert disc.bounces == 0
    assert disc.max_bounces == 4
    assert disc.damage_multiplier == 1.2
    assert disc.speed_multiplier == 1.1
    assert disc.rotation == 0.0
    assert len(disc.trail) == 0

def test_disc_projectile_update():
    """Verify DiscProjectile updates rotation and trail."""
    disc = DiscProjectile(100, 100, [1, 0], 25.0, 25.0, "owner")
    initial_pos = list(disc.location)
    
    dt = 0.016
    disc.update(dt)
    
    # Trail should have one entry (previous position)
    assert len(disc.trail) == 1
    assert disc.trail[0] == (initial_pos[0], initial_pos[1])
    
    # Rotation should have increased
    # 720 degrees/sec * 0.016 sec = 11.52 degrees
    assert disc.rotation == pytest.approx(11.52)
    
    # Update multiple times to fill trail
    for _ in range(20):
        disc.update(dt)
    
    assert len(disc.trail) == disc.max_trail_len

def test_disc_shard_behavior():
    """Verify DiscShard expires after distance/time."""
    shard = DiscShard(100, 100, [1, 0], 50.0, 10.0, "owner")
    assert shard.active
    
    # Update until expiration (max_distance = 150)
    # speed = 50.0. In one frame (dt=1/60), it moves by 50 pixels.
    # 3 frames should be 150 pixels.
    shard.update(1/60)
    assert shard.active
    shard.update(1/60)
    assert shard.active
    shard.update(1/60)
    assert not shard.active

def test_ricochet_wall_bounce():
    """Verify DiscProjectile bounces off arena boundaries."""
    arena = Arena(800, 600)
    # Width=20, so right edge is at x+20. 
    # Speed 100 * (1/60) = 1.666 pixels.
    # Initial x=779. Right edge is 799.
    # Move 1.666 -> right edge becomes 800.666. Hits wall.
    disc = DiscProjectile(779, 300, [1, 0], 100.0, 25.0, "owner")
    arena.projectiles.append(disc)
    
    initial_damage = disc.damage
    
    # Update frame
    arena.handle_collisions(1/60)
    
    # Should bounce back (direction[0] *= -1)
    assert disc.direction[0] == pytest.approx(-1.0)
    # Right edge should be at 800, so location[0] = 800 - 20 = 780
    assert disc.location[0] == pytest.approx(780)
    assert disc.bounces == 1
    assert disc.damage > initial_damage
def test_ricochet_platform_bounce():
    """Verify DiscProjectile bounces off platforms and increases stats."""
    arena = Arena(800, 600)
    # Disc moving down towards a platform
    # Platform at y=200 in world coords. Screen-y = 600 - 200 = 400.
    plat = Platform(100, 400, 200, 20) 
    arena.platforms.append(plat)
    
    # Disc at world-y 205, moving down (0, -1)
    # Speed 100 * (1/60) ≈ 1.67 pixels/frame. Need ~5 pixels to reach platform.
    # pygame.Rect truncates floats to ints, so we run multiple frames until collision.
    disc = DiscProjectile(200, 205, [0, -1], 100.0, 25.0, "owner")
    arena.projectiles.append(disc)
    
    initial_damage = disc.damage
    initial_speed = disc.speed
    
    # Run frames until disc bounces off platform
    for _ in range(10):
        arena.handle_collisions(1/60)
        if disc.bounces > 0:
            break
    
    assert disc.bounces == 1
    # Direction should be reversed (up) - positive Y in world coords
    assert disc.direction[1] > 0
    # Stats should increase after bounce
    assert disc.damage == pytest.approx(initial_damage * disc.damage_multiplier)
    assert disc.speed == pytest.approx(initial_speed * disc.speed_multiplier)
def test_ricochet_shard_spawning():
    """Verify DiscProjectile spawns shards after max bounces."""
    arena = Arena(800, 600)
    # Reach max bounces (4)
    disc = DiscProjectile(400, 300, [1, 0], 25.0, 25.0, "owner")
    disc.bounces = 4
    arena.projectiles.append(disc)
    
    # Handle collisions to trigger shard spawn
    arena.handle_collisions(0.016)
    
    # Disc should be inactive
    assert not disc.active
    assert disc not in arena.projectiles
    
    # Should have spawned 8 shards
    shards = [p for p in arena.projectiles if isinstance(p, DiscShard)]
    assert len(shards) == 8
    
    # Check radial pattern
    directions = [tuple(s.direction) for s in shards]
    # One shard should be moving right (angle 0: cos=1, sin=0)
    assert (pytest.approx(1.0), pytest.approx(0.0)) in directions
    # One shard should be moving left (angle 180: cos=-1, sin=0)
    assert (pytest.approx(-1.0), pytest.approx(0.0)) in directions

def test_ricochet_shard_damage():
    """Verify DiscShards deal damage to characters."""
    arena = Arena(800, 600)
    # Shard at (400, 300) moving right
    shard = DiscShard(400, 300, [1, 0], 50.0, 20.0, "attacker")
    arena.projectiles.append(shard)
    
    # Character in front of shard
    # Char at 410 world-x. Char width is 45.
    # Char world-y 280. 
    victim = Character("Victim", "", "", [410, 280])
    victim.id = "victim"
    arena.characters.append(victim)
    
    initial_hp = victim.health
    
    # Run collision logic
    # Shard logic in GAME_arena uses collidepoint on shard center
    arena.handle_collisions(0.016)
    
    # Expected damage: 20 raw - 5 defense = 15.
    assert victim.health == initial_hp - 15
    assert not shard.active

def test_lootpool_registration():
    """Verify that Ricochet Launcher is in the lootpool."""
    arena = setup_battle_arena()
    assert "Ricochet Launcher" in arena.lootpool, "Ricochet Launcher was not registered in the lootpool"

def test_ricochet_integration_gameplay():
    """Integration test for full disc lifecycle."""
    arena = Arena(800, 600)
    
    # Add characters
    attacker = Character("Attacker", "", "", [100, 100])
    attacker.id = "attacker"
    arena.characters.append(attacker)
    
    victim = Character("Victim", "", "", [600, 100])
    victim.id = "victim"
    arena.characters.append(victim)
    
    # Give weapon
    launcher = RicochetLauncher()
    attacker.weapon = launcher
    attacker.weapon.is_equipped = True
    
    # Add platform for bouncing
    # Platform at x=400, y=500 world coords. (Top of arena)
    plat = Platform(300, 100, 200, 20) # Rect at screen-y 100. World-y bottom = 600 - 100 - 20 = 480. Top = 500.
    arena.platforms.append(plat)
    
    # Shoot up at the platform
    # attacker at (100, 100). platform at (400, 500).
    projectiles = attacker.shoot([400, 500])
    arena.projectiles.extend(projectiles)
    
    disc = projectiles[0]
    assert isinstance(disc, DiscProjectile)
    
    # 1. Reach platform and bounce
    # Distance is ~500. Speed is 25. Takes ~20 frames.
    for _ in range(30):
        arena.handle_collisions(0.016)
        if disc.bounces > 0:
            break
    
    assert disc.bounces == 1
    
    # 2. Force max bounces to trigger explosion
    disc.bounces = 4
    arena.handle_collisions(0.016)
    
    assert not disc.active
    shards = [p for p in arena.projectiles if isinstance(p, DiscShard)]
    assert len(shards) == 8
    
    # 3. Move shards and check for hit
    # Move victim near the explosion
    # Shards spawn at disc.location.
    # One shard moves right [1, 0].
    # Victim width is 45. Place victim right where a right-moving shard will hit.
    # Disc location is center-ish.
    victim.location = [disc.location[0] + 20, disc.location[1]]
    initial_hp = victim.health
    
    # Run several frames to let shards travel
    for _ in range(10):
        arena.handle_collisions(0.016)
    
    assert victim.health < initial_hp, "Victim should have been hit by at least one shard"

def test_ricochet_edge_case_corner_fire():
    """Verify firing from a corner doesn't cause immediate stuck bouncing."""
    arena = Arena(800, 600)
    # Fire from bottom-left corner [0, 0] towards top-right [800, 600]
    launcher = RicochetLauncher()
    projectiles = launcher.shoot(0, 0, 800, 600, "player1")
    disc = projectiles[0]
    arena.projectiles.append(disc)
    
    # Update a few frames
    for _ in range(5):
        arena.handle_collisions(0.016)
    
    # Should move away from corner
    assert disc.location[0] > 0
    assert disc.location[1] > 0
    # Should not have bounced yet
    assert disc.bounces == 0
    assert disc.active


if __name__ == "__main__":
    # Allow running this file directly for quick verification
    pytest.main([__file__])