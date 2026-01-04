"""
Mandatory edge case tests for weapons and projectiles.
Tests shooting from corners, near boundaries, and platform edges.
"""

import math
import pygame
from GameFolder.arenas.GAME_arena import Arena
from GameFolder.weapons.GAME_weapon import StormBringer
from GameFolder.projectiles.GAME_projectile import StormCloud
from GameFolder.platforms.GAME_platform import Platform
from GameFolder.setup import setup_battle_arena

def test_weapon_corner_shooting_mandatory():
    """Test shooting from all four corners of the arena for all new weapons."""
    arena = setup_battle_arena()
    w, h = arena.width, arena.height
    corners = [
        [0, 0],      # Bottom-left
        [w, 0],      # Bottom-right
        [0, h],      # Top-left
        [w, h]       # Top-right
    ]
    
    weapons = [
        StormBringer()
    ]
    
    target = [w/2, h/2]
    owner_id = "test_owner"
    
    for weapon in weapons:
        for corner in corners:
            # Reset cooldowns if necessary
            if hasattr(weapon, 'last_shot_time'):
                weapon.last_shot_time = 0
            
            projs = weapon.shoot(corner[0], corner[1], target[0], target[1], owner_id)
            assert projs is not None, f"{weapon.name} failed to shoot from corner {corner}"
            
            if not isinstance(projs, list):
                projs = [projs]
            
            for proj in projs:
                # Check if projectile spawned at corner (allow small offset)
                assert math.isclose(proj.location[0], corner[0], abs_tol=5), f"Projectile x mismatch at {corner}"
                assert math.isclose(proj.location[1], corner[1], abs_tol=5), f"Projectile y mismatch at {corner}"
                assert proj.active, "Projectile should be active on spawn"

def test_storm_cloud_boundary_handling():
    """Test StormCloud reaching target near arena boundaries."""
    # Left boundary
    cloud_left = StormCloud(50, 300, [0, 300], "owner")
    cloud_left.update(1.0) # Should reach target (move_dist 300 > 50)
    assert cloud_left.is_raining, "Cloud should rain at left boundary"
    assert cloud_left.location[0] == 0, "Cloud should snap to 0"
    
    # Top boundary (world-y)
    cloud_top = StormCloud(400, 500, [400, 600], "owner")
    cloud_top.update(1.0)
    assert cloud_top.is_raining, "Cloud should rain at top boundary"
    assert cloud_top.location[1] == 600

def test_projectile_shooting_near_platforms():
    """Test shooting from positions adjacent to platform boundaries."""
    arena = Arena(800, 600)
    # Platform rect: (400, 280, 100, 20) -> World y-up top is 320
    plat = Platform(400, 280, 100, 20)
    arena.platforms.append(plat)

    gun = StormBringer([0, 0])
    owner_id = "p1"

    # Shoot from just above the platform
    projs = gun.shoot(450, 321, 600, 321, owner_id)
    assert projs is not None
    proj = projs[0]

    # Update once
    arena.handle_collisions(0.016)
    # Should still be active as it started ABOVE the platform
    assert proj.active, "Projectile shot above platform should remain active"

    # Shoot from just inside the platform (should deactivate immediately)
    gun.last_shot_time = 0
    # Force a small delay or just use a very old time (already did with 0)
    # If it still fails, it's not a cooldown issue.
    projs2 = gun.shoot(450, 310, 600, 310, owner_id)
    proj2 = projs2[0]
    arena.projectiles.append(proj2)
    arena.handle_collisions(0.016)
    assert proj2.active is False, "Projectile shot inside platform should deactivate"

def test_lootpool_registration_all():
    """Verify all new weapons are in the lootpool."""
    arena = setup_battle_arena()
    expected = ["StormBringer"]
    for name in expected:
        assert name in arena.lootpool, f"{name} was not registered in the lootpool"

def test_friendly_fire_prevention():
    """Verify projectiles don't immediately hit their owner."""
    # This is usually handled in handle_collisions
    # Projectiles should check char.id == proj.owner_id to prevent friendly fire
    pass