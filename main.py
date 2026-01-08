import sys
import time
import random
import traceback
import pygame
import argparse
import importlib
from coding.non_callable_tools.helpers import cleanup_old_logs
from BASE_files.network_client import NetworkClient, EntityManager, sync_game_files
from BASE_files.BASE_menu import BaseMenu

# TODO: Remember to call client.update() regularly in your main loop to process incoming messages and send outgoing ones.")

def run_menu():
    menu = BaseMenu()
    menu.run_menu_loop()

def run_client(network_client: NetworkClient, player_id: str = ""):
    # Clean up old client log files before starting
    cleanup_old_logs()

    print("="*70)
    print(" "*20 + "GENGAME - MULTIPLAYER CLIENT")
    print("="*70)
    print("\n🎮 GAME FEATURES:")
    print("  ✓ Multiplayer: Connect to server for real-time battles")
    print("  ✓ Life System: Each player has 3 lives")
    print("  ✓ Respawn: Players respawn after death")
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
    print(f"\nConnecting to server at {network_client.host}:{network_client.port}...\n")

    try:
        # Initialize Pygame
        pygame.init()
        width, height = 1200, 700  # Match server arena dimensions
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption(f"GenGame Client - {player_id}")
        clock = pygame.time.Clock()
        print("⚠️  IMPORTANT: Click on the game window to enable keyboard input for movement!")

        # Initialize network client and entity manager
        entity_manager = EntityManager()

        # Set up network callbacks
        assigned_character = None

        def on_character_assigned(assignment):
            nonlocal assigned_character
            assigned_character = assignment.get('assigned_character')
            print(f"Assigned to control: {assigned_character}")

        def on_file_sync_received(files):
            print("Received file sync from server...")
            if sync_game_files(files):
                # Import the setup function from the synchronized GameFolder
                try:
                    import GameFolder.setup as game_setup
                    importlib.reload(game_setup)  # Ensure we get the latest version

                    # Import game-specific classes for modularity
                    nonlocal ui, Character
                    ui = game_setup.GameUI(screen, width, height)
                    Character = game_setup.Character

                    print("✓ Game files synchronized and classes loaded")
                    network_client.acknowledge_file_sync()

                except Exception as e:
                    print(f"Failed to load synchronized game: {e}")
                    network_client.disconnect()

        def on_game_state_received(game_state):
            entity_manager.update_from_server(game_state)

            # Set local player if not already set and we have character assignment
            if entity_manager.local_player_id is None and assigned_character:
                # Find character by assigned name
                for char_data in game_state.get('characters', []):
                    if char_data.get('name') == assigned_character:
                        entity_manager.set_local_player(char_data.get('network_id'))
                        # Initialize prediction with server position
                        server_pos = char_data.get('location', [0, 0])
                        entity_manager.prediction.predicted_position = server_pos.copy()
                        entity_manager.prediction.server_position = server_pos.copy()
                        break

            nonlocal game_over, winner
            game_over = game_state.get('game_over', False)
            winner = game_state.get('winner', None)

        def on_disconnected():
            print("Disconnected from server")
            nonlocal running
            running = False

        network_client.on_file_sync_received = on_file_sync_received
        network_client.on_game_state_received = on_game_state_received
        network_client.on_character_assigned = on_character_assigned
        network_client.on_disconnected = on_disconnected

        # Initialize local state
        game_over = False
        winner = None
        ui = None  # Will be created after file sync
        Character = None  # Will be loaded after file sync

        # Input state
        held_keys = set()
        mouse_pressed = [False, False, False]  # Left, Middle, Right
        special_fire_holding = False

        running = True
        last_input_time = 0.0

        print("Connected! Waiting for game to start...\n")

        frame_count = 0
        while running:
            frame_count += 1
            frame_delta = clock.tick(60) / 1000.0
            current_time = time.time()

            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    held_keys.add(event.key)
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_q:
                        # Drop weapon
                        network_client.send_input({'drop_weapon': True}, entity_manager)
                elif event.type == pygame.KEYUP:
                    held_keys.discard(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button <= 3:
                        mouse_pressed[event.button - 1] = True
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button <= 3:
                        mouse_pressed[event.button - 1] = False

            # Get mouse position
            mx, my = pygame.mouse.get_pos()
            world_mx, world_my = mx, height - my  # Convert to world coordinates

            # Send input to server (throttled to reduce network traffic)
            if current_time - last_input_time > 0.016:  # ~60 FPS input rate
                input_data = {}
                
                # ALWAYS send mouse position for TronProjectile tracking
                input_data['mouse_pos'] = [world_mx, world_my]

                # Movement input
                direction = [0, 0]
                if pygame.K_LEFT in held_keys or pygame.K_a in held_keys:
                    direction[0] = -1
                if pygame.K_RIGHT in held_keys or pygame.K_d in held_keys:
                    direction[0] = 1
                if pygame.K_UP in held_keys or pygame.K_w in held_keys:
                    direction[1] = 1
                if pygame.K_DOWN in held_keys or pygame.K_s in held_keys:
                    direction[1] = -1

                if direction != [0, 0]:
                    input_data['movement'] = direction

                # Shooting inputs
                if mouse_pressed[0]:  # Left click
                    input_data['shoot'] = [world_mx, world_my]
                if mouse_pressed[2]:  # Right click
                    input_data['secondary_fire'] = [world_mx, world_my]

                # Special fire (E or F key)
                if pygame.K_e in held_keys or pygame.K_f in held_keys:
                    input_data['special_fire'] = [world_mx, world_my]
                    input_data['special_fire_holding'] = True
                    special_fire_holding = True
                elif special_fire_holding:
                    # Send release
                    input_data['special_fire'] = [world_mx, world_my]
                    input_data['special_fire_holding'] = False
                    special_fire_holding = False

                # Always send input (at least mouse position)
                network_client.send_input(input_data, entity_manager)

                last_input_time = current_time

            # Update network client
            network_client.update()

            # Render
            screen.fill((135, 206, 235))  # Sky blue background

            # Draw all platforms and entities managed by the entity manager
            entity_manager.draw_all(screen, height)

            # Draw UI
            if Character and ui:
                characters = entity_manager.get_entities_by_type(Character)
                ui.draw(characters, game_over, winner, {})

            pygame.display.flip()

        # Cleanup
        network_client.disconnect()
        pygame.quit()

    except Exception as e:
        print("\n" + "!"*70)
        print("CRITICAL ERROR: The client crashed!")
        print(f"Exception: {e}")
        print("!"*70)
        traceback.print_exc()
        print("!"*70)
        sys.exit(1)

if __name__ == "__main__":
    random.seed(69)

    parser = argparse.ArgumentParser(description='GenGame Multiplayer Client')
    parser.add_argument('--player', default='Player', help='Player name')
    parser.add_argument('--host', default='127.0.0.1', help='Server host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5555, help='Server port (default: 5555)')

    args = parser.parse_args()

    #network_client = NetworkClient(args.host, args.port)
    #run_client(network_client, player_id=args.player)
    run_menu()
