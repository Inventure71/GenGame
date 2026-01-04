"""
Tests for Tornado Gun and Tornado Projectile
"""

import math
import pygame
import time
from GameFolder.weapons.TornadoGun import TornadoGun
from GameFolder.projectiles.TornadoProjectile import TornadoProjectile
from GameFolder.arenas.GAME_arena import Arena
from GameFolder.characters.GAME_character import Character
from GameFolder.platforms.GAME_platform import Platform
from GameFolder.setup import setup_battle_arena

def test_tornado_gun_properties():
    """Verify TornadoGun initial properties."""
    gun = TornadoGun()
    assert gun.name == "Tornado Launcher", f"Expected 'Tornado Launcher', got {gun.name}"
    assert gun.damage == 0.8, f"Expected damage 0.8, got {gun.damage}"
    assert gun.cooldown == 4.0, f"Expected cooldown 4.0, got {gun.cooldown}"

def test_tornado_gun_shooting():
    """Verify TornadoGun spawns the correct projectile."""
    gun = TornadoGun()
    gun.last_shot_time = 0 
    projectiles = gun.shoot(100, 100, 200, 100, "player1")
    assert len(projectiles) == 1, "Should spawn exactly 1 projectile"
    assert isinstance(projectiles[0], TornadoProjectile), "Should spawn a TornadoProjectile"
    assert projectiles[0].damage == 0.8, f"Projectile should inherit gun damage 0.8, got {projectiles[0].damage}"

def test_tornado_projectile_properties():
    """Verify TornadoProjectile initial properties."""
    proj = TornadoProjectile(100, 100, [1, 0], 0.8, "player1")
    assert proj.speed == 3.0, f"Expected speed 3.0, got {proj.speed}"
    assert proj.duration == 6.0, f"Expected duration 6.0, got {proj.duration}"
    assert proj.pull_radius == 250, f"Expected pull_radius 250, got {proj.pull_radius}"

def test_tornado_projectile_update():
    """Verify TornadoProjectile movement and ground constraint."""
    # Test horizontal movement
    proj = TornadoProjectile(100, 100, [1, 0], 0.8, "player1")
    proj.update(0.1) 
    assert proj.location[0] > 100, "Projectile should move forward"
    
    # Test ground constraint (World-Y >= 0)
    proj_low = TornadoProjectile(100, -10, [1, 0], 0.8, "player1")
    proj_low.update(0.1)
    assert proj_low.location[1] == 0, f"Projectile should be constrained to y=0, got {proj_low.location[1]}"

def test_tornado_pull_mechanic():
    """Verify Arena handles Tornado conical pull on characters."""
    # Initialize pygame for Rect/Color operations if necessary
    pygame.init()
    arena = Arena(800, 600)
    # Place tornado at (400, 0)
    tornado = TornadoProjectile(400, 0, [0, 0], 10.0, "attacker")
    arena.projectiles.append(tornado)
    
    # Place character at (450, 200) - inside pull radius at that height
    # Height diff = 200. Tornado height = 400. 
    # Radius at h=200: 250 * (0.3 + 0.7 * (200/400)) = 250 * 0.65 = 162.5
    # Horizontal dist = 50. 50 < 162.5, so it should be pulled.
    char = Character("Target", "Enemy", "", [450, 200])
    char.id = "target_id"
    arena.characters.append(char)
    
    initial_x = char.location[0]
    initial_y = char.location[1]
    initial_health = char.health
    
    arena.handle_collisions(0.1)
    
    assert char.location[0] < initial_x, "Character should be pulled horizontally towards tornado center"
    assert char.location[1] > initial_y, "Character should be lifted by tornado"
    assert char.health < initial_health, "Character should take damage from tornado"

def test_tornado_weapon_pull():
    """Verify Tornado pulls weapons."""
    arena = Arena(800, 600)
    tornado = TornadoProjectile(400, 0, [0, 0], 10.0, "attacker")
    arena.projectiles.append(tornado)
    
    weapon = TornadoGun(location=[450, 100])
    arena.weapon_pickups.append(weapon)
    
    initial_x = weapon.location[0]
    initial_y = weapon.location[1]
    
    arena.handle_collisions(0.1)
    
    assert weapon.location[0] < initial_x, "Weapon should be pulled horizontally"
    assert weapon.location[1] > initial_y, "Weapon should be lifted"

def test_tornado_platform_pull():
    """Verify Tornado pulls platforms."""
    arena = Arena(800, 600)
    tornado = TornadoProjectile(400, 0, [0, 0], 10.0, "attacker")
    arena.projectiles.append(tornado)
    
    # Create a small platform. 
    # Screen height = 600. 
    # Let's place platform at Screen-Y 400. Rect(x, y, w, h)
    # Plat bottom = 450. World-Y bottom = 600 - 450 = 150.
    plat = Platform(420, 400, 50, 50, (255, 0, 0))
    arena.platforms.append(plat) # Floor is at index 0.
    
    initial_rect_x = plat.rect.x
    initial_rect_y = plat.rect.y
    
    arena.handle_collisions(0.1)
    
    # Floor at index 0 is skipped in pull logic.
    assert plat.being_pulled, "Platform should be marked as being pulled"
    assert plat.rect.centerx < 420 + 25, "Platform should move horizontally towards tornado"
    assert plat.rect.y < initial_rect_y, "Platform should move upwards (Screen-Y decreasing)"

def test_tornado_lootpool_registration():
    """Verify that Tornado Launcher is in the lootpool via setup_battle_arena."""
    arena = setup_battle_arena()
    assert "Tornado Launcher" in arena.lootpool, "Tornado Launcher was not registered in the lootpool"