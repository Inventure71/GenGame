"""
Passive ability and movement mechanic tests for MS2 cows.
"""

from GameFolder.arenas.GAME_arena import Arena
from GameFolder.characters.GAME_character import Character


def test_ruminant_regen_heals_over_time():
    """Ruminant Regen should heal the cow over time."""
    arena = Arena(400, 300, headless=True)
    char = Character("TestCow", "Test", "", [200.0, 150.0])
    arena.add_character(char)

    char.set_passive_ability("Ruminant Regen")
    char.health = max(1.0, char.health - 5.0)
    initial_health = char.health

    char.update(1.0, arena)
    assert char.health > initial_health


def test_angry_moo_triggers_damage_boost():
    """Angry Moo should boost damage multiplier when low health."""
    arena = Arena(400, 300, headless=True)
    char = Character("TestCow", "Test", "", [200.0, 150.0])
    arena.add_character(char)

    char.set_passive_ability("Angry Moo")
    baseline_multiplier = char.damage_multiplier
    char.health = char.max_health * 0.2

    char.update(0.1, arena)

    assert char.angry is True
    assert char.damage_multiplier > baseline_multiplier


def test_quick_digestion_reduces_poop_cooldown():
    """Quick Digestion should reduce the poop cooldown."""
    char = Character("TestCow", "Test", "", [100.0, 100.0])
    default_cooldown = char.poop_cooldown

    char.set_passive_ability("Quick Digestion")
    assert char.poop_cooldown < default_cooldown


def test_dash_recharges_over_time():
    """Dashes should recharge after the cooldown timer."""
    arena = Arena(400, 300, headless=True)
    char = Character("TestCow", "Test", "", [200.0, 150.0])
    arena.add_character(char)

    char.dashes_left = 0
    char.dash_recharge_timer = 0.0

    char.update(char.time_to_recharge_dash + 0.1, arena)

    assert char.dashes_left == 1
