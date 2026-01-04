import pygame
import math
from GameFolder.platforms.GAME_platform import Platform
from GameFolder.arenas.GAME_arena import Arena
from GameFolder.projectiles.BlackHoleProjectile import BlackHoleProjectile
from GameFolder.characters.GAME_character import Character

def test_platform_float_movement():
    """Test that Platform correctly handles float movement and updates its rect."""
    plat = Platform(100, 100, 50, 20)
    
    # Initial state
    assert plat.float_x == 100.0, f"Expected 100.0, got {plat.float_x}"
    assert plat.float_y == 100.0, f"Expected 100.0, got {plat.float_y}"
    assert plat.rect.x == 100, f"Expected 100, got {plat.rect.x}"
    
    # Move by float
    plat.move(5.7, -2.3)
    
    assert plat.float_x == 105.7, f"Expected 105.7, got {plat.float_x}"
    assert plat.float_y == 97.7, f"Expected 97.7, got {plat.float_y}"
    assert plat.rect.x == 105, f"Expected 105, got {plat.rect.x}"
    assert plat.rect.y == 97, f"Expected 97, got {plat.rect.y}"

def test_blackhole_stops_on_platform():
    """Test that a BlackHoleProjectile becomes stationary when hitting a platform."""
    pygame.display.init()
    pygame.display.set_mode((800, 600))
    arena = Arena(800, 600)
    
    # Add a platform in the middle
    # Note: Arena.platforms[0] is the floor. We add a new one.
    test_plat = Platform(400, 300, 100, 20)
    arena.platforms.append(test_plat)
    
    # Create projectile moving towards the platform
    # BlackHoleProjectile(x, y, target_x, target_y, owner_id)
    # The projectile's world Y is used. In screen coordinates, y=300 is 600-300 = 300.
    # Let's put the projectile just above the platform in world coordinates.
    # World Y increases upwards. Platform at screen Y=300 (top) means World Y = 600 - 300 = 300.
    # So platform occupies world Y from 280 (bottom) to 300 (top).
    
    # Projectile at world y = 310, moving towards world y = 200 (passing through the platform)
    proj = BlackHoleProjectile(450, 310, 450, 200, "test_owner")
    arena.projectiles.append(proj)
    
    assert not proj.is_stationary, "Projectile should start as non-stationary"
    
    # Step 1: Update projectile position so it collides
    # Speed is 400.0. delta_time=0.05 -> move 20 units.
    # 310 - 20 = 290. This should be inside the platform (280 to 300).
    arena.handle_collisions(0.05)
    
    # The handle_collisions method updates the projectile and then checks collision.
    # Wait, in GAME_arena.py:
    # proj.update(delta_time)
    # if not proj.is_stationary: check collision -> set is_stationary = True
    
    assert proj.is_stationary, "Projectile should be stationary after hitting platform"

def test_blackhole_pulls_floating_platform():
    """Test that a stationary BlackHoleProjectile pulls platforms (not floor)."""
    pygame.display.init()
    pygame.display.set_mode((800, 600))
    arena = Arena(800, 600)
    
    # Platform at Screen(400, 300) -> World(400, 300)
    test_plat = Platform(400, 300, 100, 20)
    arena.platforms.append(test_plat)
    
    # Black hole at Screen(450, 350) -> World(450, 250)
    # We set it to stationary immediately
    proj = BlackHoleProjectile(450, 250, 450, 250, "test_owner")
    proj.is_stationary = True
    arena.projectiles.append(proj)
    
    initial_x = test_plat.float_x
    initial_y = test_plat.float_y
    
    # Distance in screen: plat center (450, 310), bh (450, 350) -> dist = 40.
    # pull_radius is 250.
    arena.handle_collisions(0.016)
    
    assert test_plat.float_x == initial_x, "Platform should only move in Y if BH is directly below"
    assert test_plat.float_y > initial_y, "Platform should be pulled towards BH (Screen Y increases downwards)"

def test_blackhole_ignores_floor():
    """Test that the floor platform (index 0) is not pulled."""
    pygame.display.init()
    pygame.display.set_mode((800, 600))
    arena = Arena(800, 600)
    
    floor = arena.platforms[0]
    initial_x = floor.float_x
    initial_y = floor.float_y
    
    # Stationary BH near the floor
    # Floor is usually at bottom of screen.
    bh_x = floor.rect.centerx
    bh_y = 600 - floor.rect.centery + 10 # Just above/below
    proj = BlackHoleProjectile(bh_x, bh_y, bh_x, bh_y, "test_owner")
    proj.is_stationary = True
    arena.projectiles.append(proj)
    
    arena.handle_collisions(0.016)
    
    assert floor.float_x == initial_x, "Floor should not move"
    assert floor.float_y == initial_y, "Floor should not move"

def test_blackhole_pulls_character_integration():
    """Test that characters are still pulled by the black hole."""
    pygame.display.init()
    pygame.display.set_mode((800, 600))
    arena = Arena(800, 600)
    
    # Character at (100, 100)
    char = Character("Enemy", "Enemy", "", [100, 100])
    arena.characters.append(char)
    
    # Black hole at (150, 150)
    proj = BlackHoleProjectile(150, 150, 150, 150, "player")
    proj.is_stationary = True
    arena.projectiles.append(proj)
    
    initial_x = char.location[0]
    initial_y = char.location[1]
    
    # Run collision handling
    arena.handle_collisions(0.016)
    
    # Character logic in Arena uses World Coordinates for pulling:
    # dx = proj.location[0] - char.location[0] = 150 - 100 = 50
    # dy = proj.location[1] - char.location[1] = 150 - 100 = 50
    # pull_dir_x = 50 / dist
    # char.location[0] += pull_dir_x * proj.pull_strength
    
    assert char.location[0] > initial_x, "Character should be pulled in X direction"
    assert char.location[1] > initial_y, "Character should be pulled in Y direction"
    assert char.location[0] < 150, "Character should move towards BH but not pass it in one step"
    assert char.location[1] < 150, "Character should move towards BH but not pass it in one step"

def test_blackhole_gun_registration():
    """Verify that BlackHoleGun is registered in the arena."""
    pygame.display.init()
    pygame.display.set_mode((800, 600))
    arena = Arena(800, 600)
    
    assert "BlackHoleGun" in arena.lootpool, "BlackHoleGun was not registered in the lootpool"
    assert arena.lootpool["BlackHoleGun"] is not None, "BlackHoleGun provider is missing"

def test_platform_return_to_origin():
    """Test that platforms move back to their original position when not being pulled."""
    arena = Arena(800, 600)
    # Platform at (100, 100)
    plat = Platform(100, 100, 50, 20)
    arena.platforms.append(plat)
    
    # Manually move it
    plat.move(50, 50)
    assert plat.float_x == 150.0
    assert plat.float_y == 150.0
    
    # Call handle_collisions which should trigger return_to_origin since being_pulled is False
    arena.handle_collisions(0.1)
    
    assert plat.float_x < 150.0, "Platform should be moving back towards original X"
    assert plat.float_y < 150.0, "Platform should be moving back towards original Y"