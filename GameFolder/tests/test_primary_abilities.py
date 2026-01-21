"""
Primary ability tests for MS2 cows.
"""

from GameFolder.arenas.GAME_arena import Arena
from GameFolder.characters.GAME_character import Character
from GameFolder.effects.GAME_effects import ConeEffect, RadialEffect, WaveProjectileEffect
from GameFolder.pickups.GAME_pickups import PRIMARY_ABILITY_NAMES


def test_primary_ability_mapping():
    """All primary ability names should map to a callable."""
    char = Character("TestCow", "Test", "", [100.0, 100.0])

    for ability_name in PRIMARY_ABILITY_NAMES:
        char.set_primary_ability(ability_name)
        assert char.primary_ability is not None
        assert char.primary_ability_name == ability_name
        assert char.available_primary_abilities == char.max_primary_abilities


def test_milk_splash_creates_cone_effect():
    """Milk Splash should spawn a ConeEffect."""
    arena = Arena(500, 400, headless=True)
    char = Character("TestCow", "Test", "", [200.0, 200.0])
    arena.add_character(char)

    char.set_primary_ability("Milk Splash")
    arena.current_time = 1.0
    char.use_primary_ability(arena, [250.0, 220.0])

    assert any(isinstance(effect, ConeEffect) for effect in arena.effects)


def test_stomp_creates_radial_effect():
    """Stomp should spawn a RadialEffect."""
    arena = Arena(500, 400, headless=True)
    char = Character("TestCow", "Test", "", [200.0, 200.0])
    arena.add_character(char)

    char.set_primary_ability("Stomp")
    arena.current_time = 1.0
    char.use_primary_ability(arena, [200.0, 200.0])

    assert any(isinstance(effect, RadialEffect) for effect in arena.effects)


def test_moo_of_doom_creates_wave():
    """Moo of Doom should spawn a WaveProjectileEffect."""
    arena = Arena(500, 400, headless=True)
    char = Character("TestCow", "Test", "", [200.0, 200.0])
    arena.add_character(char)

    char.set_primary_ability("Moo of Doom")
    arena.current_time = 1.0
    char.use_primary_ability(arena, [300.0, 200.0])

    assert any(isinstance(effect, WaveProjectileEffect) for effect in arena.effects)
