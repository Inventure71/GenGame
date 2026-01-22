"""
Edge case tests for MS2 effects and safe zone logic.
"""

from GameFolder.arenas.GAME_arena import Arena
from GameFolder.characters.GAME_character import Character
from GameFolder.effects.radialeffect import RadialEffect
from GameFolder.effects.waveprojectileeffect import WaveProjectileEffect


def test_safe_zone_damage_tick():
    """Characters outside the safe zone should take periodic damage."""
    arena = Arena(300, 300, headless=True)
    arena.safe_damage_interval = 0.0
    arena.safe_zone.center = [0.0, 0.0]
    arena.safe_zone.target_center = [0.0, 0.0]
    arena.safe_zone.radius = 10.0

    char = Character("TestCow", "Test", "", [200.0, 200.0])
    arena.add_character(char)

    initial_health = char.health
    arena.update(0.1)

    assert char.health < initial_health


def test_effect_damage_cooldown():
    """Effects should respect damage cooldown per target."""
    arena = Arena(400, 300, headless=True)
    char = Character("TestCow", "Test", "", [200.0, 150.0])
    arena.add_character(char)
    
    # Resolve obstacles first to get the character's final position
    # (obstacle collisions move the character before effects are applied)
    arena.handle_collisions()
    # Now place the effect at the character's actual location
    char_final_location = char.location[:]
    
    effect = RadialEffect(char_final_location, radius=60, owner_id="enemy", damage=5, damage_cooldown=1.0)
    arena.add_effect(effect)

    arena.current_time = 1.0
    initial_health = char.health
    arena.handle_collisions()
    first_hit_health = char.health

    arena.current_time += 0.5
    arena.handle_collisions()

    assert first_hit_health < initial_health
    assert char.health == first_hit_health

    arena.current_time += 1.0
    arena.handle_collisions()
    assert char.health < first_hit_health


def test_wave_projectile_expires_at_max_distance():
    """WaveProjectileEffect should expire once it travels max_distance."""
    wave = WaveProjectileEffect([100.0, 100.0], angle=0.0, max_distance=20, speed=10, owner_id="cow", damage=5)
    expired = wave.update(0.2)
    assert expired is True
