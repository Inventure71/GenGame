import pygame
import time
import sys
import traceback
from BASE_files.network_client import NetworkClient, EntityManager, sync_game_files
from BASE_components.BASE_camera import BaseCamera

DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720

def run_client(network_client: NetworkClient, player_id: str = ""):
    print("="*70)
    print(" "*20 + "CORE CONFLICT - MULTIPLAYER CLIENT")
    print("="*70)
    print("\n🎮 GAME FEATURES:")
    print("  ✓ Multiplayer: Connect to server for real-time battles")
    print("  ✓ Life System: Single-life elimination")
    print("  ✓ Safe Zone: Shrinking circle damages cows outside")
    print("  ✓ Abilities: Pick up primary/passive abilities around the map")
    print("  ✓ Growth: Eat grass to grow and find extra ability charges")
    print("  ✓ Pooping: Drop poop mines or walls based on passives")
    print("\n🎯 CONTROLS:")
    print("  Arrow Keys / WASD: Move Cow")
    print("  Mouse Left-Click: Use primary ability (if available)")
    print("  Mouse Right-Click: Secondary action (if mapped)")
    print("  Space: Eat grass")
    print("  Shift: Dash")
    print("  P: Poop")
    print("  ESC: Quit game")
    print("="*70)
    print(f"\nConnecting to server at {network_client.host}:{network_client.port}...\n")

    try:
        # Check if client is connected
        if not network_client or not network_client.connected:
            print("[error] Network client not connected! Cannot start game.")
            return

        # Initialize Pygame (safe to call multiple times)
        pygame.init()
        # Disable key repeat for precise game control
        pygame.key.set_repeat()
        width, height = DEFAULT_WIDTH, DEFAULT_HEIGHT  # Viewport dimensions
        screen = pygame.display.set_mode(
            (width, height),
            pygame.FULLSCREEN | pygame.DOUBLEBUF,
            vsync=1,
        )
        pygame.display.set_caption(f"Core Conflict Client - {player_id}")
        clock = pygame.time.Clock()
        print("[warning]  IMPORTANT: Click on the game window to enable keyboard input for movement!")

        # Initialize network client and entity manager
        entity_manager = EntityManager()

        # Set up network callbacks
        assigned_character = None

        def on_character_assigned(assignment):
            nonlocal assigned_character
            assigned_character = assignment.get('assigned_character')
            print(f"Assigned to control: {assigned_character}")

        def reload_game_classes():
            """Reload game classes from GameFolder after patches are applied."""
            try:
                from BASE_files.BASE_menu_helpers import reload_game_code
                reloaded_setup = reload_game_code()
                
                if reloaded_setup:
                    # Import game-specific classes for modularity
                    nonlocal ui, Character, world_width, world_height, camera
                    entity_manager.clear() # Clear old entities before reloading
                    ui = reloaded_setup.GameUI(screen, width, height)
                    Character = reloaded_setup.Character
                    world_width = getattr(reloaded_setup, "WORLD_WIDTH", DEFAULT_WIDTH)
                    world_height = getattr(reloaded_setup, "WORLD_HEIGHT", DEFAULT_HEIGHT)
                    camera.set_world_size(world_width, world_height)
                    
                    print("✓ Game classes deep reloaded after patch application")
                else:
                    print("[warning] Failed to deep reload game classes")

            except Exception as e:
                print(f"Failed to reload game classes: {e}")

        def on_file_sync_received(files):
            print("Received file sync from server...")
            if sync_game_files(files):
                # Import the setup function from the synchronized GameFolder
                try:
                    from BASE_files.BASE_menu_helpers import reload_game_code
                    reloaded_setup = reload_game_code()
                    
                    if reloaded_setup:
                        # Import game-specific classes for modularity
                        nonlocal ui, Character, world_width, world_height, camera
                        entity_manager.clear() # Clear old entities before reloading
                        ui = reloaded_setup.GameUI(screen, width, height)
                        Character = reloaded_setup.Character
                        world_width = getattr(reloaded_setup, "WORLD_WIDTH", DEFAULT_WIDTH)
                        world_height = getattr(reloaded_setup, "WORLD_HEIGHT", DEFAULT_HEIGHT)
                        camera.set_world_size(world_width, world_height)
                        
                        print("✓ Game files synchronized and classes deep reloaded")
                        # Set flag immediately to prevent race condition
                        network_client.file_sync_complete = True
                        network_client.acknowledge_file_sync()
                    else:
                        print("[warning] Failed to deep reload after file sync")
                        # Acknowledge even on failure to prevent getting stuck
                        network_client.acknowledge_file_sync()
                        network_client.disconnect()

                except Exception as e:
                    print(f"Failed to load synchronized game: {e}")
                    # Acknowledge even on exception to prevent getting stuck
                    network_client.acknowledge_file_sync()
                    network_client.disconnect()
            else:
                print("[error] Failed to sync game files")
                # Acknowledge even on failure to prevent getting stuck
                network_client.acknowledge_file_sync()
                network_client.disconnect()

        def on_game_start():
            """Callback when game start is received - ensure classes are loaded."""
            print("Game start received - ensuring classes are loaded...")

            try:
                from BASE_files.BASE_menu_helpers import reload_game_code
                reloaded_setup = reload_game_code()
                
                if reloaded_setup:
                    nonlocal ui, Character, world_width, world_height, camera
                    entity_manager.clear() # Clear old entities before reloading
                    ui = reloaded_setup.GameUI(screen, width, height)
                    Character = reloaded_setup.Character
                    world_width = getattr(reloaded_setup, "WORLD_WIDTH", DEFAULT_WIDTH)
                    world_height = getattr(reloaded_setup, "WORLD_HEIGHT", DEFAULT_HEIGHT)
                    camera.set_world_size(world_width, world_height)
                    
                    print("✓ Game classes deep reloaded for game start")
                else:
                    print("[warning] Failed to deep reload for game start")

            except Exception as e:
                print(f"Failed to reload game classes for game start: {e}")

        def on_game_state_received(game_state):
            try:
                entity_manager.update_from_server(game_state)
            except Exception as e:
                print(f"[warning] Failed to apply game state: {e}")
                network_client.request_full_state()
                return

            # Set local player if not already set and we have character assignment
            if entity_manager.local_player_id is None and assigned_character:
                # Find character by assigned name/id (games may use either field)
                for char_data in game_state.get('characters', []) or []:
                    if char_data.get('name') == assigned_character or char_data.get('id') == assigned_character:
                        entity_manager.set_local_player(char_data.get('network_id'))
                        # Initialize prediction with server position
                        server_pos = char_data.get('location', [0, 0])
                        entity_manager.prediction.predicted_position = server_pos.copy()
                        entity_manager.prediction.server_position = server_pos.copy()
                        break

            nonlocal game_over, winner
            game_over = game_state.get('game_over', False)
            winner = game_state.get('winner_id', game_state.get('winner', None))

        def on_disconnected():
            print("Disconnected from server")
            nonlocal running
            running = False

        def on_game_restarting(winner, restart_delay, message):
            print(f"🏆 Game finished! Winner: {winner}")
            print(f"⏳ {message}")
            # Don't exit yet - wait for server_restarted message

        def on_server_restarted(message):
            print(f"🔄 {message}")
            nonlocal running
            running = False  # Exit the game client to return to menu

        network_client.on_file_sync_received = on_file_sync_received
        network_client.on_game_start = on_game_start
        network_client.on_game_state_received = on_game_state_received
        network_client.on_character_assigned = on_character_assigned
        network_client.on_disconnected = on_disconnected
        network_client.on_game_restarting = on_game_restarting
        network_client.on_server_restarted = on_server_restarted

        # Initialize local state
        game_over = False
        winner = None
        ui = None  # Will be created after file sync
        Character = None  # Will be loaded after file sync
        world_width = DEFAULT_WIDTH
        world_height = DEFAULT_HEIGHT
        camera = BaseCamera(world_width, world_height, width, height)

        # Input state
        held_keys = set()
        mouse_pressed = [False, False, False]  # Left, Middle, Right

        running = True
        last_input_time = 0.0

        print("Connected! Waiting for game to start...\n")

        # Request file synchronization from server
        network_client.request_file_sync()

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
            if camera:
                world_mx, world_my = camera.screen_to_world_point(mx, my)
            else:
                world_mx, world_my = mx, height - my  # Convert to world coordinates

            # Send input to server (throttled to reduce network traffic)
            if current_time - last_input_time > 0.016:  # ~60 FPS input rate
                # Use the Character class to determine what to send
                # This allows agents to define new keys in GAME_character.py
                if Character and hasattr(Character, 'get_input_data'):
                    input_data = Character.get_input_data(held_keys, mouse_pressed, [world_mx, world_my])
                else:
                    # Fallback if Character class is not loaded yet
                    input_data = {'mouse_pos': [world_mx, world_my], 'movement': [0, 0]}

                # Always include raw input context for modular key/mouse handling
                input_data.setdefault('mouse_pos', [world_mx, world_my])
                input_data.setdefault('held_keys', sorted(list(held_keys)))
                input_data.setdefault('mouse_buttons', list(mouse_pressed))

                # Always send input (at least mouse position)
                network_client.send_input(input_data, entity_manager)

                last_input_time = current_time

            # Update network client
            network_client.update()

            # Update camera to follow local player (fallback to first entity)
            follow_entity = None
            if entity_manager.local_player_id:
                follow_entity = entity_manager.get_entity(entity_manager.local_player_id)
            if follow_entity is None and entity_manager.entities:
                follow_entity = next(iter(entity_manager.entities.values()))
            if follow_entity and hasattr(follow_entity, 'location'):
                camera.set_center(follow_entity.location[0], follow_entity.location[1])

            # Render
            screen.fill((20, 90, 20))  # Grass green background

            # Draw all platforms and entities managed by the entity manager
            entity_manager.draw_all(screen, world_height, camera=camera)

            # Draw UI
            if Character and ui:
                characters = entity_manager.get_entities_by_type(Character)
                network_stats = network_client.get_packet_stats() if network_client else None
                ui.draw(characters, game_over, winner, {}, local_player_id=entity_manager.local_player_id, network_stats=network_stats)

            pygame.display.flip()

        # Cleanup
        network_client.disconnect()
        # Don't quit pygame here - let the menu handle it
        print("Game client exited cleanly")

    except Exception as e:
        print("\n" + "!"*70)
        print("CRITICAL ERROR: The client crashed!")
        print(f"Exception: {e}")
        print("!"*70)
        traceback.print_exc()
        print("!"*70)
        sys.exit(1)
