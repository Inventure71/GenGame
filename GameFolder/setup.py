from GameFolder.arenas.GAME_arena import Arena
from GameFolder.characters.GAME_character import Character
from GameFolder.platforms.GAME_platform import Platform
from GameFolder.ui.GAME_ui import GameUI
from GameFolder.weapons.GAME_weapon import Weapon, StormBringer
from GameFolder.weapons.BlackHoleGun import BlackHoleGun
from GameFolder.weapons.OrbitalCannon import OrbitalCannon
from GameFolder.weapons.TornadoGun import TornadoGun

def setup_battle_arena(width: int = 1200, height: int = 700, headless: bool = False):
    """
    Initializes and sets up the entire arena with platforms, players, and lootpool.
    This can be modified here in GameFolder while main.py stays clean. 
    This function can be modified but it needs to be named setup_battle_arena.
    Most importantly this is the only function that will be called so if a separate class of arena exists, it needs to be imported here and setup here.
    
    Args:
        width: Arena width in pixels (default: 1200)
        height: Arena height in pixels (default: 700)
        headless: If True, runs without graphics/display (default: False)
    
    Returns:
        Arena: Configured arena instance ready for gameplay
    """
    arena = Arena(width, height, headless=headless)
    
    # 1. Add Players
    player1 = Character(name="Player1", description="Green", image="", location=[150, 140], width=45, height=45)
    player1.color = (50, 255, 100)
    
    player2 = Character(name="Player2", description="Red", image="", location=[1000, 140], width=45, height=45)
    player2.color = (255, 100, 100)
    
    arena.add_character(player1)
    arena.add_character(player2)
    
    # 2. Add Platforms
    platforms = [
        Platform(100, 120, 200, 20), Platform(900, 120, 200, 20),
        Platform(250, 250, 180, 20), Platform(500, 300, 200, 20), Platform(770, 250, 180, 20),
        Platform(150, 400, 150, 20), Platform(900, 400, 150, 20),
        Platform(450, 500, 300, 20), Platform(300, 600, 150, 20), Platform(750, 600, 150, 20),
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