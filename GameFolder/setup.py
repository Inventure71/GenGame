from GameFolder.arenas.GAME_arena import Arena
from GameFolder.characters.GAME_character import Character
from GameFolder.platforms.GAME_platform import Platform
from GameFolder.ui.GAME_ui import GameUI
from GameFolder.weapons.GAME_weapon import Weapon, StormBringer
from GameFolder.weapons.BlackHoleGun import BlackHoleGun
from GameFolder.weapons.OrbitalCannon import OrbitalCannon
from GameFolder.weapons.TornadoGun import TornadoGun

def setup_battle_arena(width: int = 1200, height: int = 700, headless: bool = False, player_names: list = None):
    """
    Initializes and sets up the entire arena with platforms, players, and lootpool.
    This can be modified here in GameFolder while main.py stays clean.
    This function can be modified but it needs to be named setup_battle_arena.
    Most importantly this is the only function that will be called so if a separate class of arena exists, it needs to be imported here and setup here.

    Args:
        width: Arena width in pixels (default: 1200)
        height: Arena height in pixels (default: 700)
        headless: If True, runs without graphics/display (default: False)
        player_names: List of player names to create characters for (default: None, uses ["Player1", "Player2"])

    Returns:
        Arena: Configured arena instance ready for gameplay
    """
    arena = Arena(width, height, headless=headless)

    # Default player names if none provided
    if player_names is None:
        player_names = ["Player1", "Player2"]

    # Player colors and positions
    player_configs = [
        {"color": (50, 255, 100), "location": [150, 140], "description": "Green"},
        {"color": (255, 100, 100), "location": [1000, 140], "description": "Red"},
        {"color": (100, 100, 255), "location": [150, 500], "description": "Blue"},
        {"color": (255, 255, 100), "location": [1000, 500], "description": "Yellow"},
        {"color": (255, 100, 255), "location": [575, 320], "description": "Purple"},
        {"color": (100, 255, 255), "location": [575, 100], "description": "Cyan"},
    ]

    # 1. Add Players
    for i, player_name in enumerate(player_names):
        if i < len(player_configs):
            config = player_configs[i]
            player = Character(name=player_name, description=config["description"], image="",
                             location=config["location"], width=45, height=45)
            player.color = config["color"]
            arena.add_character(player)
            print(f"Created character: {player_name} ({config['description']}) at {config['location']}")
        else:
            # Fallback for more than 6 players
            x_pos = 150 + (i % 3) * 400
            y_pos = 140 + (i // 3) * 200
            player = Character(name=player_name, description=f"Player {i+1}", image="",
                             location=[x_pos, y_pos], width=45, height=45)
            player.color = (255, 255, 255)  # White as fallback
            arena.add_character(player)
            print(f"Created character: {player_name} (fallback) at [{x_pos}, {y_pos}]")
    
    # 2. Add Platforms
    platforms = [
        Platform(100, 120, 200, 20), Platform(900, 120, 200, 20),
        Platform(250, 250, 180, 20), Platform(500, 300, 200, 20), Platform(770, 250, 180, 20),
        Platform(150, 400, 150, 20), Platform(900, 400, 150, 20),
        Platform(450, 500, 300, 20), Platform(300, 600, 150, 20), Platform(750, 600, 150, 20),
        # Large bottom platform - 3/4 arena width (900px), centered
        Platform(150, 650, 900, 30),
    ]
    for p in platforms: arena.add_platform(p)
    
    # 3. Setup Lootpool
    # Standard weapons using factory functions
    #arena.register_weapon_type("Pistol", lambda loc: Weapon("Pistol", damage=12, cooldown=0.3, projectile_speed=25.0, location=loc))
    
    # Special weapons classes
    arena.register_weapon_type("StormBringer", StormBringer)
    arena.register_weapon_type("BlackHoleGun", BlackHoleGun)
    arena.register_weapon_type("Orbital Cannon", OrbitalCannon)
    arena.register_weapon_type("Tornado Launcher", TornadoGun)

    arena.spawn_weapon(OrbitalCannon([100, 100]))
    
    return arena