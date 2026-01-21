"""
Basic functionality tests for MS2 core systems.
Covers characters, grass eating, poop, abilities, and pickups.
"""

from GameFolder.arenas.GAME_arena import Arena
from GameFolder.characters.GAME_character import Character
from GameFolder.effects.GAME_effects import RadialEffect, ObstacleEffect


def test_character_creation():
    """Test that a character can be created with MS2 defaults."""
    char = Character("TestCow", "Test", "", [100.0, 200.0], width=30, height=30)

    assert char.name == "TestCow"
    assert char.location == [100.0, 200.0]
    assert char.size == 30.0
    assert char.max_health == 60.0
    assert char.health == char.max_health
    assert char.is_alive is True
    assert char.is_eliminated is False


def test_eat_grass_increases_size():
    """Eating grass should consume food and increase size."""
    arena = Arena(800, 600, headless=True)
    char = Character("TestCow", "Test", "", [100.0, 100.0])
    arena.add_character(char)

    field = arena.grass_fields[0]
    char.location = field.world_center[:]

    initial_size = char.size
    initial_food = field.current_food

    char.try_eat(arena)

    assert char.size > initial_size
    assert field.current_food == initial_food - 1
    assert char.eat_cooldown > 0


def test_poop_creates_obstacle_effect():
    """Pooping should spawn an ObstacleEffect and reduce size."""
    arena = Arena(800, 600, headless=True)
    char = Character("TestCow", "Test", "", [200.0, 200.0])
    arena.add_character(char)

    initial_size = char.size
    char.try_poop(arena)

    assert char.size < initial_size
    assert any(isinstance(effect, ObstacleEffect) for effect in arena.effects)


def test_dash_consumes_charge():
    """Dashing should consume a dash charge."""
    arena = Arena(800, 600, headless=True)
    char = Character("TestCow", "Test", "", [150.0, 150.0])
    arena.add_character(char)

    char.dashes_left = 2
    char.move([1, 0], arena, mouse_pos=None, dash=True)

    assert char.dashes_left == 1


def test_primary_ability_spawns_effect():
    """Using Stomp should add a RadialEffect to the arena."""
    arena = Arena(800, 600, headless=True)
    char = Character("TestCow", "Test", "", [300.0, 300.0])
    arena.add_character(char)

    char.set_primary_ability("Stomp")
    arena.current_time = 1.0
    char.use_primary_ability(arena, [300.0, 300.0])

    assert any(isinstance(effect, RadialEffect) for effect in arena.effects)


def test_ability_pickup_assigns_ability():
    """Colliding with an ability pickup should assign it and remove pickup."""
    arena = Arena(800, 600, headless=True)
    char = Character("TestCow", "Test", "", [0.0, 0.0])
    arena.add_character(char)

    pickup = next((p for p in arena.weapon_pickups if p.ability_type == "primary"), None)
    if pickup is None:
        pickup = arena.weapon_pickups[0]

    char.location = pickup.location[:]
    arena.handle_collisions()

    assert pickup not in arena.weapon_pickups
    assert pickup.is_active is False

    if pickup.ability_type == "primary":
        assert char.primary_ability_name == pickup.ability_name
    else:
        assert char.passive_ability_name == pickup.ability_name
