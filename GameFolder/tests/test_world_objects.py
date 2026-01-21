"""
World object tests for obstacles and grass fields.
"""

from GameFolder.arenas.GAME_arena import Arena
from GameFolder.characters.GAME_character import Character
from GameFolder.world.GAME_world_objects import WorldObstacle, GrassField


def test_grass_eat_and_regrow():
    """Grass should be consumable and regrow over time."""
    grass = GrassField(100.0, 100.0, radius=20.0, max_food=3, arena_height=300)

    assert grass.current_food == 3
    assert grass.eat() is True
    assert grass.current_food == 2

    grass.regrow(5.0, rate=1.0)
    assert grass.current_food == 3


def test_slowing_obstacle_sets_slowed():
    """Slowing obstacles should mark cows as slowed."""
    arena = Arena(400, 300, headless=True)
    arena.obstacles = []
    arena.platforms = []

    obstacle = WorldObstacle(200.0, 150.0, size=80, obstacle_type="slowing", arena_height=arena.height)
    arena.obstacles.append(obstacle)
    arena.platforms.append(obstacle)

    char = Character("TestCow", "Test", "", [200.0, 150.0])
    arena.add_character(char)

    arena.handle_collisions()
    assert char.is_slowed is True


def test_blocking_obstacle_pushes_out():
    """Blocking obstacles should push overlapping cows out."""
    arena = Arena(400, 300, headless=True)
    arena.obstacles = []
    arena.platforms = []

    obstacle = WorldObstacle(200.0, 150.0, size=80, obstacle_type="blocking", arena_height=arena.height)
    arena.obstacles.append(obstacle)
    arena.platforms.append(obstacle)

    char = Character("TestCow", "Test", "", [200.0, 150.0])
    arena.add_character(char)

    initial_location = char.location[:]
    arena.handle_collisions()

    assert char.location != initial_location
