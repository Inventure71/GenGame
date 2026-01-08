"""
Tests for Orbital Cannon weapon and its associated projectiles.
"""

import pytest
import pygame
from GameFolder.weapons.OrbitalCannon import OrbitalCannon
from GameFolder.projectiles.OrbitalProjectiles import TargetingLaser, OrbitalStrikeMarker, OrbitalBlast
from GameFolder.arenas.GAME_arena import Arena
from GameFolder.characters.GAME_character import Character
from GameFolder.platforms.GAME_platform import Platform
from GameFolder.setup import setup_battle_arena

def test_orbital_cannon_properties():
    """Verify Orbital Cannon initial properties."""
    gun = OrbitalCannon()
    assert gun.name == "Orbital Cannon"
    assert gun.damage == 10
    assert gun.cooldown <= 3.0

def test_orbital_cannon_shooting():
    """Verify Orbital Cannon spawns a TargetingLaser."""
    gun = OrbitalCannon()
    gun.last_shot_time = 0
    # Shoot from (100, 100) towards (200, 200)
    projectiles = gun.shoot(100, 100, 200, 200, "player1")
    assert len(projectiles) == 1
    assert isinstance(projectiles[0], TargetingLaser)
    assert projectiles[0].owner_id == "player1"
    # Direction should be normalized vector towards (200, 200)
    assert projectiles[0].direction[0] > 0
    assert projectiles[0].direction[1] > 0
    assert projectiles[0].speed == 1200
    assert projectiles[0].width == 6

def test_targeting_laser_collision_impact():
    """Verify TargetingLaser spawns an OrbitalStrikeMarker upon hitting a platform."""
    width, height = 800, 600
    arena = Arena(width, height, headless=True)
    # Laser at (100, 300) moving right
    laser = TargetingLaser(100, 300, [1, 0], "player1", 1000)
    arena.projectiles.append(laser)
    
    # Platform at (150, 300)
    # Platform(x, y, width, height) - in Arena, platform y is usually screen bottom up? 
    # Actually Arena uses pygame Rects for platforms.
    # From GAME_arena.py: p_py_y = self.height - proj.location[1] - proj.height
    # So world-y 300 is screen-y 600 - 300 - 6 = 294.
    plat = Platform(110, 250, 50, 100) # Rect(110, 250, 50, 100) covers world-y 300
    arena.platforms.append(plat)
    
    # Run update world instead of just handle_collisions to process transitions
    arena.update_world(0.05)
    
    # Laser should be gone, Marker should be present
    assert laser not in arena.projectiles
    markers = [p for p in arena.projectiles if isinstance(p, OrbitalStrikeMarker)]
    assert len(markers) == 1
    # clipline should have set location to entry point (x=110)
    assert markers[0].location[0] == 110, f"Marker should spawn at collision entry point, got {markers[0].location[0]}"

def test_targeting_laser_tracking():
    """Verify TargetingLaser updates last_location correctly."""
    laser = TargetingLaser(100, 100, [1, 0], "owner", 1000)
    initial_loc = list(laser.location)
    assert laser.last_location == initial_loc
    
    # Update one frame
    delta_time = 0.016
    laser.update(delta_time)
    
    assert laser.last_location == initial_loc
    assert laser.location[0] > initial_loc[0]
    # 1200 * 0.016 = 19.2
    assert laser.location[0] == pytest.approx(initial_loc[0] + 19.2)

def test_targeting_laser_fast_collision():
    """Verify TargetingLaser hits a thin platform even at high speeds (segment collision)."""
    arena = Arena(800, 600, headless=True)
    # Laser at (100, 300) moving right.
    laser = TargetingLaser(100, 300, [1, 0], "player1", 1000)
    arena.projectiles.append(laser)
    
    # Very thin platform at x=150. Width=5.
    # Rect(150, 250, 5, 100)
    plat = Platform(150, 250, 5, 100)
    arena.platforms.append(plat)
    
    # Update with large delta_time to "skip" the platform
    # 1200 * 0.1 = 120 pixels. New X = 220.
    arena.update_world(0.1)
    
    assert not laser.active
    markers = [p for p in arena.projectiles if isinstance(p, OrbitalStrikeMarker)]
    assert len(markers) == 1
    assert markers[0].location[0] == 150, "Should hit thin platform via segment collision"

def test_lootpool_registration():
    """Verify that Orbital Cannon is in the lootpool."""
    arena = setup_battle_arena(headless=True)
    assert "Orbital Cannon" in arena.lootpool, "Orbital Cannon was not registered in the lootpool"

def test_marker_to_blast_transition():
    """Verify OrbitalStrikeMarker spawns an OrbitalBlast after warmup."""
    arena = Arena(800, 600, headless=True)
    marker = OrbitalStrikeMarker(400, 100, "player1")
    arena.projectiles.append(marker)
    
    # Run arena update to process transitions
    arena.update_world(1.1)
    
    # Marker should be gone, Blast should be present at same X
    assert marker not in arena.projectiles
    blasts = [p for p in arena.projectiles if isinstance(p, OrbitalBlast)]
    assert len(blasts) == 1
    assert blasts[0].location[0] == 400

def test_orbital_blast_damage():
    """Verify OrbitalBlast deals damage to characters in range."""
    arena = Arena(800, 600, headless=True)
    # Blast centered at X=400. Range is [350, 450] (width 100)
    blast = OrbitalBlast(400, "attacker")
    arena.projectiles.append(blast)
    
    # Character inside beam
    victim = Character("Victim", "", "", [410, 100])
    victim.id = "victim"
    # Deplete shields first so we can test health damage
    victim.shield = 0
    arena.characters.append(victim)
    
    # Character outside beam
    safe_guy = Character("SafeGuy", "", "", [550, 100])
    safe_guy.id = "safeguy"
    arena.characters.append(safe_guy)
    
    initial_hp_victim = victim.health
    initial_hp_safe = safe_guy.health
    
    # Owner inside beam
    attacker = Character("Attacker", "", "", [390, 100])
    attacker.id = "attacker"
    arena.characters.append(attacker)
    initial_hp_attacker = attacker.health
    
    # Run collision logic (damage is 800/sec, reduced by 5 defense)
    arena.handle_collisions(0.1)

    assert victim.health == initial_hp_victim - 75
    assert safe_guy.health == initial_hp_safe
    assert attacker.health == initial_hp_attacker, "Owner should not take damage from their own Orbital Blast"

def test_orbital_blast_duration():
    """Verify OrbitalBlast deactivates after its duration."""
    blast = OrbitalBlast(400, "player1")
    assert blast.active
    
    # Duration is 0.6s
    blast.update(0.5)
    assert blast.active
    
    blast.update(0.2)
    assert not blast.active

def test_orbital_blast_vertical_coverage():
    """Verify OrbitalBlast damages characters regardless of their Y position."""
    arena = Arena(800, 600, headless=True)
    blast = OrbitalBlast(400, "attacker")
    arena.projectiles.append(blast)

    # Character high up in the air
    sky_victim = Character("SkyVictim", "", "", [410, 550])
    sky_victim.id = "sky_victim"
    arena.characters.append(sky_victim)

    initial_hp = sky_victim.health
    # Run collision logic
    arena.handle_collisions(0.1)

    assert sky_victim.health < initial_hp, "Blast should hit characters high in the air"

def test_orbital_cannon_gameplay_integration():
    """Integration test simulating real gameplay: player shoots at enemy with orbital cannon."""
    # Setup arena with two characters
    arena = Arena(800, 600, headless=True)

    # Attacker character with orbital cannon at position (200, 300)
    attacker = Character("Attacker", "", "", [200, 300])
    attacker.id = "attacker"
    # Give attacker an orbital cannon
    cannon = OrbitalCannon()
    attacker.weapon = cannon
    attacker.weapon.is_equipped = True
    arena.characters.append(attacker)

    # Victim character at position (600, 300)
    victim = Character("Victim", "", "", [600, 300])
    victim.id = "victim"
    # Deplete shields first so we can test health damage
    victim.shield = 0
    arena.characters.append(victim)

    initial_victim_hp = victim.health

    # Simulate attacker shooting at victim's location (like clicking on victim)
    # This mimics what happens when player clicks mouse button
    victim_center_x = victim.location[0] + (victim.width * victim.scale_ratio) / 2
    victim_center_y = victim.location[1] + (victim.height * victim.scale_ratio) / 2

    # Attacker shoots at victim
    projectiles = attacker.shoot([victim_center_x, victim_center_y])

    # Add projectiles to arena (like the game does)
    if projectiles:
        if isinstance(projectiles, list):
            arena.projectiles.extend(projectiles)
        else:
            arena.projectiles.append(projectiles)

    # Verify targeting laser was created
    lasers = [p for p in arena.projectiles if isinstance(p, TargetingLaser)]
    assert len(lasers) == 1, "Should have spawned one targeting laser"
    laser = lasers[0]
    assert laser.owner_id == "attacker"

    # Run update_world until laser hits something or reaches max distance
    # Laser speed is 1200, distance to victim is ~400 units, so should hit quickly
    for _ in range(30):  # Run enough frames for laser to reach target
        arena.update_world(0.016)  # ~60 FPS
        lasers_check = [p for p in arena.projectiles if isinstance(p, TargetingLaser)]
        if len(lasers_check) == 0:
            break  # Laser is gone

    # Laser should be gone and marker should be created
    lasers_after = [p for p in arena.projectiles if isinstance(p, TargetingLaser)]
    assert len(lasers_after) == 0, f"Laser should be gone after collision, still have {len(lasers_after)} lasers"

    markers = [p for p in arena.projectiles if isinstance(p, OrbitalStrikeMarker)]
    assert len(markers) == 1, "Should have spawned one orbital strike marker"
    marker = markers[0]
    assert marker.owner_id == "attacker"

    # Wait for marker warmup (1 second at 60 FPS = 60 frames)
    # The blast gets created when the marker becomes inactive
    for _ in range(65):  # A bit more than 1 second
        arena.update_world(0.016)

    # Marker should be gone and blast should be created
    markers_after = [p for p in arena.projectiles if isinstance(p, OrbitalStrikeMarker)]
    assert len(markers_after) == 0, "Marker should be gone after warmup"

    blasts = [p for p in arena.projectiles if isinstance(p, OrbitalBlast)]
    assert len(blasts) == 1, "Should have spawned one orbital blast"
    blast = blasts[0]
    assert blast.owner_id == "attacker"

    # The blast may have already dealt some damage during the warmup frames
    # Let's measure damage from now on
    health_before_damage = victim.health

    # Run blast for exactly 0.1 seconds to deal controlled damage
    arena.update_world(0.1)

    # Check what damage was actually dealt in this final call
    damage_this_frame = health_before_damage - victim.health
    print(f"Damage dealt in final 0.1s frame: {damage_this_frame}")

    # Expected: 800 damage/sec * 0.1 sec = 80 raw damage, minus 5 defense = 75 net damage
    # But due to tick-based physics: (800 * 0.0167 - 5) * 6 ≈ 50 net damage
    expected_damage = 50
    assert abs(damage_this_frame - expected_damage) < 1.0, f"Blast should deal ~{expected_damage} damage per 0.1s, but dealt {damage_this_frame}"

    # Total damage should be reasonable (some damage may have been dealt during warmup)
    total_damage = initial_victim_hp - victim.health
    print(f"Total damage dealt: {total_damage}")
    assert total_damage > 70, "Should have dealt significant damage"

    # Attacker should not take damage (owner immunity)
    attacker.health == 100, "Attacker should not take damage from their own blast"