import random
from GameFolder.arenas.GAME_arena import Arena
from GameFolder.characters.GAME_character import Character
from GameFolder.ui.GAME_ui import GameUI
from BASE_components.BASE_arena import WORLD_WIDTH, WORLD_HEIGHT # DO NOT MANUALLY CHANGE THESE VALUES, NO MATTER WHAT THE INSTRUCTIONS ARE.

def setup_battle_arena(width: int = WORLD_WIDTH, height: int = WORLD_HEIGHT, headless: bool = False, player_names: list = None):
    random.seed(69)
    arena = Arena(width, height, headless=headless)

    if player_names is None:
        player_names = ["Player1", "Player2"]

    def pick_spawn():
        for _ in range(20):
            x = random.uniform(80, width - 80)
            y = random.uniform(80, height - 80)
            blocked = False
            for obstacle in arena.obstacles:
                if abs(x - obstacle.world_center[0]) < obstacle.size / 2 + 30 and abs(y - obstacle.world_center[1]) < obstacle.size / 2 + 30:
                    blocked = True
                    break
            if not blocked:
                return [x, y]
        return [width / 2, height / 2]

    for name in player_names:
        spawn = pick_spawn()
        player = Character(name=name, description="Cow", image="", location=spawn, width=30, height=30)
        arena.add_character(player)

    return arena
