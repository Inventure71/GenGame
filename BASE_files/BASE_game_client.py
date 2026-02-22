import pygame
import time
import sys
import traceback
from BASE_files.BASE_menu_helpers import get_fullscreen_size
from BASE_files.network_client import NetworkClient, EntityManager, sync_game_files
from BASE_components.BASE_arena import WORLD_WIDTH, WORLD_HEIGHT
from BASE_components.BASE_camera import BaseCamera
from BASE_components.BASE_asset_handler import AssetHandler
from BASE_components.BASE_spatial import SpatialGrid

FULLSCREEN = True

class ClientArena:
    """Mock arena for client-side prediction."""
    def __init__(self, width, height, entity_manager=None):
        self.width = width
        self.height = height
        self.entity_manager = entity_manager
        self.grass_fields = []
        self.weapon_pickups = []
        self.projectiles = []
        self.effects = []
        self.current_time = time.time()
        self.headless = False
        
        # Spatial partitioning for optimized collision
        self.spatial_grid = SpatialGrid(cell_size=250)

    def update_spatial_grid(self):
        """Rebuild spatial grid with all relevant objects for prediction."""
        if not self.entity_manager:
            self.spatial_grid.clear()
            return
            
        self.spatial_grid.clear()
        
        # We need to import these to check instances, but do it locally to avoid import cycles
        from GameFolder.world.GAME_world_objects import GrassField, WorldObstacle
        from GameFolder.pickups.GAME_pickups import AbilityPickup

        # 1. Platforms (Grass, Obstacles)
        for platform in self.entity_manager.platforms.values():
            # Add obstacles (checking obstacle_type is good, but isinstance is safer for WorldObstacle)
            if hasattr(platform, 'obstacle_type') or isinstance(platform, WorldObstacle):
                self.spatial_grid.add(platform)
            # Add grass fields (CRITICAL for eating to work on client)
            elif isinstance(platform, GrassField):
                self.spatial_grid.add(platform)
        
        # 2. Entities (Pickups, Effects, Poop Walls)
        for entity in self.entity_manager.entities.values():
            # Pickups (CRITICAL for swapping abilities)
            if isinstance(entity, AbilityPickup):
                if getattr(entity, 'is_active', True):
                    self.spatial_grid.add(entity)
            
            # Effects / Obstacles
            elif hasattr(entity, 'obstacle_type') or hasattr(entity, 'wall'):
                self.spatial_grid.add(entity)

    def add_effect(self, effect):
        pass
        
    def handle_collisions(self, cow):
        """Perform client-side collision resolution for prediction."""
        if not cow:
            return

        # Basic boundary check
        margin = cow.size / 2 if hasattr(cow, 'size') else 15
        cow.location[0] = max(margin, min(self.width - margin, cow.location[0]))
        cow.location[1] = max(margin, min(self.height - margin, cow.location[1]))

        # Get nearby objects from spatial grid (optimized)
        cow_radius = margin
        nearby = self.spatial_grid.get_nearby(cow.location[0], cow.location[1], cow_radius + 50)

        # Obstacle collision (Circle-Circle or Rect)
        for obstacle in nearby:
            # 1. Standard Obstacles (WorldObstacle)
            # Only collide if explicitly blocking. GrassField has no obstacle_type.
            if hasattr(obstacle, 'obstacle_type'):
                if obstacle.obstacle_type != 'blocking':
                    continue
            # 2. Poop Walls (ObstacleEffect)
            elif hasattr(obstacle, 'wall'):
                if not obstacle.wall:
                    continue
            # 3. Skip everything else (Grass, Pickups, non-wall Effects)
            else:
                continue
                
            obs_size = getattr(obstacle, 'size', getattr(obstacle, 'width', 0))
            obstacle_radius = obs_size / 2
            
            # Position resolution (optimized coordinate fetching)
            ox, oy = 0, 0
            if hasattr(obstacle, 'world_center'):
                ox, oy = obstacle.world_center
            elif hasattr(obstacle, 'location'):
                ox, oy = obstacle.location
            elif hasattr(obstacle, 'rect'):
                ox, oy = obstacle.rect.centerx, obstacle.rect.centery
            elif hasattr(obstacle, 'float_x'):
                ox = obstacle.float_x + getattr(obstacle, 'width', 0) / 2
                oy = obstacle.float_y + getattr(obstacle, 'height', 0) / 2
            else: continue

            dx = cow.location[0] - ox
            dy = cow.location[1] - oy
            distance_sq = dx * dx + dy * dy
            radius_sum = cow_radius + obstacle_radius
            
            if distance_sq < radius_sum * radius_sum:
                import math
                distance = math.sqrt(distance_sq)
                if distance == 0:
                    dx, dy = 1, 0
                    distance = 1.0
                else:
                    dx /= distance
                    dy /= distance
                
                overlap = radius_sum - distance
                cow.location[0] += dx * overlap
                cow.location[1] += dy * overlap

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
    print("  Q: Swap ability with pickup underfoot")
    print("  Hold H: Ability details")
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
        width, height = get_fullscreen_size()  # Match VNC/display so noVNC shows full screen
        screen = pygame.display.set_mode(
            (width, height),
            pygame.FULLSCREEN if FULLSCREEN else 0 | pygame.DOUBLEBUF,
            vsync=1,
        )
        pygame.display.set_caption(f"Core Conflict Client - {player_id}")
        clock = pygame.time.Clock()
        print("[warning]  IMPORTANT: Click on the game window to enable keyboard input for movement!")

        # Initialize network client and entity manager
        entity_manager = EntityManager(network_client)

        # Set up network callbacks
        assigned_character = player_id or None
        assigned_network_id = None

        def on_character_assigned(assignment):
            nonlocal assigned_character, assigned_network_id
            assigned_character = assignment.get('assigned_character')
            assigned_network_id = assignment.get('assigned_network_id')
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
                    world_width = getattr(reloaded_setup, "WORLD_WIDTH", WORLD_WIDTH)
                    world_height = getattr(reloaded_setup, "WORLD_HEIGHT", WORLD_HEIGHT)
                    camera.set_world_size(world_width, world_height)
                    load_background()  # Reload background with new world size
                    
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
                        world_width = getattr(reloaded_setup, "WORLD_WIDTH", WORLD_WIDTH)
                        world_height = getattr(reloaded_setup, "WORLD_HEIGHT", WORLD_HEIGHT)
                        camera.set_world_size(world_width, world_height)
                        load_background()  # Load background with world size
                        
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
                    world_width = getattr(reloaded_setup, "WORLD_WIDTH", WORLD_WIDTH)
                    world_height = getattr(reloaded_setup, "WORLD_HEIGHT", WORLD_HEIGHT)
                    camera.set_world_size(world_width, world_height)
                    load_background()  # Load background with world size
                    
                    print("✓ Game classes deep reloaded for game start")
                else:
                    print("[warning] Failed to deep reload for game start")

            except Exception as e:
                print(f"Failed to reload game classes for game start: {e}")

        def on_game_state_received(game_state):
            nonlocal game_over, winner, assigned_network_id
            try:
                entity_manager.update_from_server(game_state)
            except Exception as e:
                print(f"[warning] Failed to apply game state: {e}")
                network_client.request_full_state()
                return

            # Resolve local player from assignment, even if network IDs change mid-session.
            desired_network_id = None
            if assigned_network_id and assigned_network_id in entity_manager.entities:
                desired_network_id = assigned_network_id

            if desired_network_id is None and assigned_character:
                # Find character by assigned name/id (games may use either field)
                for char_data in game_state.get('characters', []) or []:
                    if char_data.get('name') == assigned_character or char_data.get('id') == assigned_character:
                        desired_network_id = char_data.get('network_id')
                        if desired_network_id:
                            assigned_network_id = desired_network_id
                        break

            local_entity = None
            if entity_manager.local_player_id:
                local_entity = entity_manager.get_entity(entity_manager.local_player_id)
                if assigned_character and local_entity is not None:
                    local_id = getattr(local_entity, "id", None)
                    local_name = getattr(local_entity, "name", None)
                    if local_id != assigned_character and local_name != assigned_character:
                        local_entity = None

            if (entity_manager.local_player_id is None or local_entity is None) and desired_network_id:
                entity_manager.set_local_player(desired_network_id)
                # Initialize prediction with server position if already present
                entity = entity_manager.get_entity(desired_network_id)
                if entity and hasattr(entity, "location"):
                    server_pos = entity.location
                    entity_manager.prediction.predicted_position = list(server_pos)
                    entity_manager.prediction.server_position = list(server_pos)

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
        if network_client.last_character_assignment:
            on_character_assigned(network_client.last_character_assignment)

        # Initialize local state
        game_over = False
        winner = None
        ui = None  # Will be created after file sync
        Character = None  # Will be loaded after file sync
        world_width = WORLD_WIDTH
        world_height = WORLD_HEIGHT
        camera = BaseCamera(world_width, world_height, width, height)
        
        # Background will be loaded after world dimensions are known
        background_tile = None
        background_tile_size = None
        background_variant = None
        
        def load_background():
            """Load background tile for infinite tiling."""
            nonlocal background_tile, background_tile_size, background_variant
            # Try to load random background from background category (at original size for tiling)
            bg_surface, loaded, variant = AssetHandler.get_image_from_category(
                "background",
                variant=None,  # Pick random variant
                frame=0,
                size=None,  # Load at original size for tiling
            )
            if loaded and bg_surface is not None:
                # Store the tile image and its size for infinite tiling
                background_tile = bg_surface
                background_tile_size = bg_surface.get_size()
                background_variant = variant

        # Input state
        held_keys = set()
        mouse_pressed = [False, False, False]  # Left, Middle, Right

        running = True
        last_input_time = 0.0
        
        # Client-side prediction arena
        client_arena = ClientArena(world_width, world_height, entity_manager)

        print("Connected! Waiting for game to start...\n")

        # Request file synchronization from server
        network_client.request_file_sync()

        frame_count = 0
        while running:
            frame_count += 1
            frame_delta = clock.tick(60) / 1000.0
            current_time = time.time()
            
            # Update client arena time
            client_arena.current_time = current_time
            # Update dimensions in case they changed (reloaded)
            client_arena.width = world_width
            client_arena.height = world_height
            # Cache everything for this frame to optimize prediction
            client_arena.update_spatial_grid()

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

                # Client-Side Prediction: Apply input locally immediately
                local_entity = None
                if entity_manager.local_player_id:
                    local_entity = entity_manager.get_entity(entity_manager.local_player_id)
                
                if local_entity and hasattr(local_entity, 'process_input'):
                    # Save state before prediction for reconciliation check (optional, skipping for now)
                    local_entity.process_input(input_data, client_arena)
                    # Apply collision resolution immediately after movement
                    client_arena.handle_collisions(local_entity)

                # Always send input (at least mouse position)
                network_client.send_input(input_data, entity_manager)

                last_input_time = current_time

            # Update network client
            network_client.update()
            
            # Reconciliation: Check if server state arrived and corrects us
            if entity_manager.local_player_id:
                local_entity = entity_manager.get_entity(entity_manager.local_player_id)
                if local_entity and hasattr(local_entity, 'server_location') and hasattr(local_entity, 'last_server_input_id'):
                    # Server state is authoritative.
                    # 1. Snap to server location
                    # Only snap if the error is significant to avoid micro-jitters from floating point
                    # or if we want perfect sync. For fluid movement, snapping + replay is standard.
                    
                    # Store current predicted pos to check error (debug)
                    # pred_x, pred_y = local_entity.location
                    
                    # Snap
                    local_entity.location = list(local_entity.server_location)
                    
                    # 2. Replay all inputs that happened AFTER the server's last processed input
                    inputs_to_replay = entity_manager.prediction.reconcile_with_server({
                        'last_input_id': local_entity.last_server_input_id
                    })
                    
                    if inputs_to_replay:
                        for inp in inputs_to_replay:
                            if hasattr(local_entity, 'process_input'):
                                local_entity.process_input(inp, client_arena)
                                # Apply collision resolution during replay too
                                client_arena.handle_collisions(local_entity)
                    
                    # Clear server state flags to avoid re-reconciling same state
                    # Actually, we should keep them until new state arrives?
                    # No, update_from_server sets them. If we process them once, we shouldn't process again
                    # unless they change. But update_from_server is called asynchronously.
                    # Ideally, network_client.update() populates the queue, and we process it.
                    # But entity_manager.update_from_server updates the entity directly.
                    # So we just reconcile every frame? No, that would be wasteful.
                    # Ideally only when new state arrives.
                    # But here we are in the main loop.
                    # Let's consume the reconciliation trigger.
                    delattr(local_entity, 'server_location')
            
            # Update entities for client-side animation (characters need to update animation frames)
            for entity in entity_manager.entities.values():
                if hasattr(entity, 'update'):
                    # Create a dummy arena object for update() call if needed
                    # Most entities just need delta_time for animation
                    try:
                        entity.update(frame_delta, None)
                    except (TypeError, AttributeError):
                        # Some entities might not need arena parameter
                        pass

            # Update camera to follow local player (fallback to first entity)
            follow_entity = None
            if entity_manager.local_player_id:
                follow_entity = entity_manager.get_entity(entity_manager.local_player_id)
            if follow_entity is None and entity_manager.entities:
                follow_entity = next(iter(entity_manager.entities.values()))
            if follow_entity and hasattr(follow_entity, 'location'):
                camera.set_center(follow_entity.location[0], follow_entity.location[1])

            # Render
            # Draw background image if available, otherwise use green color
            if background_tile is not None and camera is not None:
                # Get camera viewport in world coordinates
                left, bottom, right, top = camera.get_viewport()
                
                bg_width, bg_height = background_tile_size
                
                # Calculate which tiles we need to draw (infinite tiling)
                # Start from the leftmost/bottommost tile that intersects the viewport
                start_tile_x = int(left // bg_width)
                start_tile_y = int(bottom // bg_height)
                end_tile_x = int((right + bg_width - 1) // bg_width)
                end_tile_y = int((top + bg_height - 1) // bg_height)
                
                # Draw all tiles that intersect the viewport
                for tile_y in range(start_tile_y, end_tile_y + 1):
                    for tile_x in range(start_tile_x, end_tile_x + 1):
                        # Calculate world position of this tile
                        tile_world_x = tile_x * bg_width
                        tile_world_y = tile_y * bg_height
                        
                        # Convert to screen coordinates
                        screen_x, screen_y = camera.world_to_screen_point(tile_world_x, tile_world_y + bg_height)
                        screen_x = int(screen_x)
                        screen_y = int(screen_y)
                        
                        # Calculate how much of this tile is visible in world coordinates
                        tile_left = max(left, tile_world_x)
                        tile_bottom = max(bottom, tile_world_y)
                        tile_right = min(right, tile_world_x + bg_width)
                        tile_top = min(top, tile_world_y + bg_height)
                        
                        # Calculate source rect within the tile (tile surface uses y-down)
                        # Tile surface: y=0 at top, y=bg_height at bottom
                        # World: tile_world_y is bottom, tile_world_y + bg_height is top
                        src_x = int(tile_left - tile_world_x)
                        # Convert from world y-up to tile surface y-down
                        # Visible area in world: from tile_bottom (low y) to tile_top (high y)
                        # In tile surface: top of visible = bg_height - (tile_top - tile_world_y)
                        #                  bottom of visible = bg_height - (tile_bottom - tile_world_y)
                        src_y = int(bg_height - (tile_top - tile_world_y))
                        src_width = int(tile_right - tile_left)
                        src_height = int(tile_top - tile_bottom)
                        
                        # Calculate destination on screen (convert world coords to screen coords)
                        # world_to_screen_point converts: screen_y = top - world_y
                        # So for tile_top (high world y), we get low screen y (top of screen)
                        # We want to draw at the top of the visible area on screen
                        dest_x, dest_y = camera.world_to_screen_point(tile_left, tile_top)
                        dest_x = int(dest_x)
                        dest_y = int(dest_y)
                        
                        # Blit the visible portion of this tile
                        if src_width > 0 and src_height > 0:
                            src_rect = pygame.Rect(src_x, src_y, src_width, src_height)
                            screen.blit(background_tile, (dest_x, dest_y), area=src_rect)
            elif background_tile is not None:
                # No camera, just tile the background (shouldn't happen in normal gameplay)
                bg_width, bg_height = background_tile_size
                for y in range(0, height, bg_height):
                    for x in range(0, width, bg_width):
                        screen.blit(background_tile, (x, y))
            else:
                screen.fill((20, 90, 20))  # Grass green background fallback

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
