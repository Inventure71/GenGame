from GameFolder.setup import setup_battle_arena

def main():
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
    print("  Arrow Keys / WASD: Move Player 1")
    print("  Mouse Left-Click: Shoot (if you have a weapon)")
    print("  Q: Drop current weapon")
    print("  ESC: Quit game")
    print("\n💡 TIPS:")
    print("  - You can only hold 1 weapon at a time")
    print("  - Press Q to drop your current weapon")
    print("  - Walk over a weapon to pick it up (only when not holding one)")
    print("="*70)
    print("\nStarting game...\n")
    
    # Initialize and setup the arena via the child's setup function
    # This keeps main.py clean and delegates specific setup to the GameFolder
    arena = setup_battle_arena()
    
    print(f"✓ Created {len(arena.characters)} players")
    print(f"✓ Spawned {len(arena.platforms)} platforms")
    print(f"✓ Lootpool initialized with: {list(arena.lootpool.keys())}")
    print("\n💡 Look for weapons on the ground - they'll have their names displayed!")
    print("   Walk over them to pick them up!\n")
    print("Let the battle begin! 🎯\n")
    
    # Start the game loop
    arena.run()

if __name__ == "__main__":
    main()

