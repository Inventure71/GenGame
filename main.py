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
    print("\n🌐 NETWORK:")
    print("  Server: Runs simulation at 60Hz, broadcasts state at 30Hz via UDP")
    print("  Client: Sends inputs at 30Hz, renders at 60Hz with interpolation")
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

        if is_server:
            print(f"[MODE] Starting as SERVER on port 5555 (UDP: 5556)")
            arena.start_server(("0.0.0.0", 5555))
        else:
            print(f"[MODE] Starting as CLIENT, connecting to localhost:5555")
            try:
                arena.connect_to_server(("localhost", 5555))
                print(f"✓ Connected! Assigned ID: {arena.numeric_id}")
            except Exception as e:
                print(f"✗ Failed to connect: {e}")
                print("  Make sure the server is running first!")
                sys.exit(1)
        
        # Start the game loop
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

    if len(sys.argv) < 2:
        print("Usage: python main.py server|client [name]")
        print("  server - Start as game server (Player1)")
        print("  client - Connect to server (Player2)")
        sys.exit(1)

    if sys.argv[1] == "server":
        main(player_id="Player1", is_server=True)
    elif sys.argv[1] == "client":
        main(player_id="Player2", is_server=False)
    else:
        print(f"Unknown mode: {sys.argv[1]}")
        print("Use 'server' or 'client'")
        sys.exit(1)
