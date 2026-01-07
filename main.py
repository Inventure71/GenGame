import sys
import time
import random
import traceback
from GameFolder.setup import setup_battle_arena

def main(player_id: str = "", is_server: bool = False):
    print("="*70)
    print(" "*20 + "GENGAME - BATTLE ARENA")
    print("="*70)
    print("\n🎮 GAME FEATURES:")
    print("  ✓ Life System: Each player has 3 lives")
    print("  ✓ Respawn: Players respawn at center-top after death")
    print("  ✓ Weapon Pickups: Walk over weapons to pick them up!")
    print("  ✓ UI: Shows health, lives, and current weapon")
    print("  ✓ Winner: Last player standing wins!")
    print("\n🎯 CONTROLS:")
    print("  Arrow Keys / WASD: Move Player")
    print("  Mouse Left-Click: Primary Fire (if you have a weapon)")
    print("  Mouse Right-Click: Secondary Fire")
    print("  E/F: Special Fire")
    print("  Q: Drop current weapon")
    print("  ESC: Quit game")
    print("="*70)
    print("\nStarting game...\n")

    try:
        # Initialize and setup the arena via the child's setup function
        arena = setup_battle_arena()

        # Set the local player ID so we can control a character
        arena.set_id(player_id)

        print(f"✓ Created {len(arena.characters)} players")
        print(f"✓ Spawned {len(arena.platforms)} platforms")
        print(f"✓ Lootpool initialized with: {list(arena.lootpool.keys())}")
        print("\n💡 Look for weapons on the ground - they'll have their names displayed!")
        print("   Walk over them to pick them up!\n")
        print("Let the battle begin! 🎯\n")

        # Start the local game loop
        arena.run()
        
    except Exception as e:
        print("\n" + "!"*70)
        print("CRITICAL ERROR: The game crashed!")
        print("!"*70)
        traceback.print_exc()
        print("!"*70)
        sys.exit(1)

if __name__ == "__main__":
    random.seed(69)

    player_name = "Player"
    if len(sys.argv) > 1:
        player_name = sys.argv[1]

    main(player_id=player_name)
