from GameFolder.arenas.GAME_arena import Arena
from GameFolder.characters.GAME_character import Character
from GameFolder.platforms.GAME_platform import Platform
from GameFolder.ui.GAME_ui import GameUI
from GameFolder.weapons.GAME_weapon import Weapon, StormBringer
from GameFolder.weapons.BlackHoleGun import BlackHoleGun
from GameFolder.weapons.OrbitalCannon import OrbitalCannon
from GameFolder.weapons.TornadoGun import TornadoGun
from GameFolder.weapons.Pistol import Pistol

def setup_battle_arena(width: int = 1400, height: int = 900, headless: bool = False, player_names: list = None):
    """
    Initializes and sets up the entire arena with platforms, players, and lootpool.
    This can be modified here in GameFolder while main.py stays clean.
    This function can be modified but it needs to be named setup_battle_arena.
    Most importantly this is the only function that will be called so if a separate class of arena exists, it needs to be imported here and setup here.

    Args:
        width: Arena width in pixels (default: 1600)
        height: Arena height in pixels (default: 900)
        headless: If True, runs without graphics/display (default: False)
        player_names: List of player names to create characters for (default: None, uses ["Player1", "Player2"])

    Returns:
        Arena: Configured arena instance ready for gameplay
    """
    arena = Arena(width, height, headless=headless)

    # Default player names if none provided
    if player_names is None:
        player_names = ["Player1", "Player2"]

    # Player colors and positions - properly positioned on platforms for 1400x900 arena
    player_configs = [
        {"color": (50, 255, 100), "location": [408, 129], "description": "Green"},  # On bottom-left platform (screen X=350-525, Y=771)
        {"color": (255, 100, 100), "location": [933, 129], "description": "Red"},  # On bottom-right platform (screen X=875-1050, Y=771)
        {"color": (100, 100, 255), "location": [641, 515], "description": "Blue"},  # On middle platform (screen X=583-816, Y=385)
        {"color": (255, 255, 100), "location": [956, 515], "description": "Yellow"},  # On middle platform (screen X=898-1108, Y=385)
        {"color": (255, 100, 255), "location": [731, 450], "description": "Purple"},  # On center platform (screen X=656-831, Y=450)
        {"color": (100, 255, 255), "location": [634, 643], "description": "Cyan"},  # On high platform (screen X=175-306, Y=257)
    ]

    # 1. Add Players
    for i, player_name in enumerate(player_names):
        if i < len(player_configs):
            config = player_configs[i]
            player = Character(name=player_name, description=config["description"], image="",
                             location=config["location"], width=30, height=30)
            player.color = config["color"]
            arena.add_character(player)
            print(f"Created character: {player_name} ({config['description']}) at {config['location']}")
        else:
            # Fallback for more than 6 players
            x_pos = 150 + (i % 3) * 400
            y_pos = 140 + (i // 3) * 200
            player = Character(name=player_name, description=f"Player {i+1}", image="",
                             location=[x_pos, y_pos], width=30, height=30)
            player.color = (255, 255, 255)  # White as fallback
            arena.add_character(player)
            print(f"Created character: {player_name} (fallback) at [{x_pos}, {y_pos}]")
    
    # 2. Add Platforms - properly scaled for 1400x900 arena from original 1200x700
    platforms = [
        # Top row - scaled from original
        Platform(116, 154, 233, 20), Platform(1050, 154, 233, 20),
        # Middle rows - scaled positions
        Platform(291, 321, 210, 20), Platform(583, 385, 233, 20), Platform(898, 321, 210, 20),
        Platform(175, 514, 175, 20), Platform(1050, 514, 175, 20),
        Platform(525, 642, 350, 20), Platform(350, 771, 175, 20), Platform(875, 771, 175, 20),
        # Additional platforms for larger arena
        Platform(175, 257, 131, 20), Platform(1094, 257, 131, 20),  # Extra top platforms
        Platform(656, 450, 175, 20),  # Center platform
        Platform(88, 600, 131, 20), Platform(1181, 600, 131, 20),  # Side platforms
        # Large bottom platform - 3/4 arena width (1050px), centered at 175
        Platform(175, 835, 1050, 30),
    ]
    for p in platforms: arena.add_platform(p)
    
    # 3. Setup Lootpool
    # Standard weapons using factory functions
    arena.register_weapon_type("Pistol", Pistol)

    # Special weapons classes
    arena.register_weapon_type("StormBringer", StormBringer)
    arena.register_weapon_type("BlackHoleGun", BlackHoleGun)
    arena.register_weapon_type("Orbital Cannon", OrbitalCannon)
    arena.register_weapon_type("Tornado Launcher", TornadoGun)

    arena.spawn_weapon(OrbitalCannon([117, 746]))
    
    return arena