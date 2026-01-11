import pygame
import sys
import random
import time
from typing import Dict, List, Optional, Tuple, Set
from BASE_components.BASE_character import BaseCharacter
from BASE_components.BASE_platform import BasePlatform
from BASE_components.BASE_ui import BaseUI
from BASE_components.BASE_projectile import BaseProjectile
from GameFolder.weapons.Pistol import Pistol


class Arena:
    """
    Base Arena for local single-player gameplay.
    """

    # Game tick rate
    TICK_RATE = 60  # Game simulation Hz
    
    def __init__(self, width: int = 800, height: int = 600, headless: bool = False):
        self.headless = headless
        self.width = width
        self.height = height

        # Only initialize pygame/display if not headless
        if not self.headless:
            pygame.init()
            self.screen = pygame.display.set_mode((self.width, self.height))
            pygame.display.set_caption("GenGame Arena")
            self.clock = pygame.time.Clock()
        else:
            self.screen = None
            self.clock = None

        self.running = True
        
        # Game entities
        self.characters: List[BaseCharacter] = []
        self.platforms: List[BasePlatform] = []
        self.projectiles = []
        self.weapon_pickups = []
        self.ammo_pickups = []  # List of ammo pickups
        
        # Entity maps
        self.characters_map: Dict[str, BaseCharacter] = {}  # name -> character
        
        # Input state
        self.held_keycodes = set()
        
        # Camera
        self.camera_offset = [0.0, 0.0]
        
        # Game state
        self.game_over = False
        self.winner = None
        self.respawn_timer: Dict[str, float] = {}
        self.respawn_delay = 2.0
        
        # Game timing
        self.game_tick = 0
        self.last_tick_time = 0.0
        self.tick_interval = 1.0 / self.TICK_RATE
        self.tick_accumulator = 0.0
        
        
        # UI (only initialize if not headless)
        if not self.headless:
            self.ui = BaseUI(self.screen, self.width, self.height)
        else:
            self.ui = None
        
        # Default floor - 90% width, centered horizontally
        floor_width = int(self.width * 0.9)
        floor_x = int(self.width * 0.05)
        self.platforms.append(BasePlatform(floor_x, self.height, floor_width, 20, (50, 50, 50)))

        # Weapon spawning
        self.lootpool: Dict[str, callable] = {}
        self.weapon_spawn_timer = 0.0
        self.spawn_interval = 8.0
        self.spawn_count = 0
        
        # Ammo spawning
        self.ammo_spawn_timer = 0.0
        self.ammo_spawn_interval = 12.0  # Spawn ammo every 12 seconds
        self.ammo_spawn_count = 0
        
        # Weapon name -> ID mapping for binary protocol
        self.weapon_name_to_id: Dict[str, int] = {}
        self.weapon_id_to_name: Dict[int, str] = {}
        self.next_weapon_id = 1
        
        # Projectile type mapping
        self.projectile_type_map: Dict[type, int] = {}
        self.projectile_id_to_type: Dict[int, type] = {}
        self.next_proj_type_id = 1

    def set_id(self, player_id: str):
        """Set the player's name."""
        self.id = player_id
        pygame.display.set_caption(f"GenGame - {self.id if self.id else 'Player'}")

    def register_weapon_type(self, name: str, weapon_provider):
        """Register a weapon type in the lootpool."""
        self.lootpool[name] = weapon_provider
        # Assign numeric ID for binary protocol
        if name not in self.weapon_name_to_id:
            self.weapon_name_to_id[name] = self.next_weapon_id
            self.weapon_id_to_name[self.next_weapon_id] = name
            self.next_weapon_id += 1

    def register_projectile_type(self, proj_class: type):
        """Register a projectile type for binary serialization."""
        if proj_class not in self.projectile_type_map:
            self.projectile_type_map[proj_class] = self.next_proj_type_id
            self.projectile_id_to_type[self.next_proj_type_id] = proj_class
            self.next_proj_type_id += 1


    # =========================================================================
    # COORDINATE CONVERSION
    # =========================================================================
    
    def screen_to_world(self, screen_x: float, screen_y: float) -> Tuple[float, float]:
        world_x = screen_x + self.camera_offset[0]
        world_y = (self.height - screen_y) + self.camera_offset[1]
        return world_x, world_y
    
    def world_to_screen(self, world_x: float, world_y: float) -> Tuple[float, float]:
        screen_x = world_x - self.camera_offset[0]
        screen_y = self.height - (world_y - self.camera_offset[1])
        return screen_x, screen_y

    # =========================================================================
    # ENTITY MANAGEMENT
    # =========================================================================

    def add_character(self, character: BaseCharacter):
        self.characters.append(character)
        self.characters_map[character.name] = character

    def add_platform(self, platform: BasePlatform):
        self.platforms.append(platform)



                
    def _update_simulation(self, delta_time: float):
        """Run one tick of physics simulation."""
        self.manage_weapon_spawns(delta_time)
        self.manage_ammo_spawns(delta_time)
        self.handle_respawns(delta_time)
        self.check_winner()
        
        for char in self.characters:
            char.update(delta_time, self.platforms, self.height, self.width)
        
        self.update_projectiles(delta_time)
        self.handle_collisions(delta_time)











    # =========================================================================
    # COMMON GAME LOGIC
    # =========================================================================

    def handle_respawns(self, delta_time: float):
        for char in self.characters:
            if not char.is_alive and not char.is_eliminated:
                if char.id not in self.respawn_timer:
                    self.respawn_timer[char.id] = self.respawn_delay
                self.respawn_timer[char.id] -= delta_time
                if self.respawn_timer[char.id] <= 0:
                    respawn_x = self.width / 2
                    respawn_y = self.height - 100
                    char.respawn([respawn_x, respawn_y], self)  # Pass arena for pistol spawning
                    del self.respawn_timer[char.id]

    def check_winner(self):
        if self.game_over: return
        alive = [char for char in self.characters if not char.is_eliminated]
        if len(alive) == 1:
            self.winner = alive[0]
            self.game_over = True
            print(f"GAME OVER! {self.winner.name} WINS!")
        elif len(alive) == 0:
            self.game_over = True

    def update_projectiles(self, delta_time: float):
        """Update all active projectiles."""
        new_projectiles = []
        for proj in self.projectiles[:]:
            result = proj.update(delta_time)
            if isinstance(result, list): new_projectiles.extend(result)
            elif result: new_projectiles.append(result)

            if (proj.location[0] < -200 or proj.location[0] > self.width + 200 or 
                proj.location[1] < -200 or proj.location[1] > self.height + 200):
                if proj in self.projectiles: self.projectiles.remove(proj)
        
        if new_projectiles:
            self.projectiles.extend(new_projectiles)

    def handle_collisions(self, delta_time: float = 0.016):
        """Handle collisions."""
        for proj in self.projectiles[:]:
            if not proj.active:
                if proj in self.projectiles: self.projectiles.remove(proj)
                continue
            
            p_rect = pygame.Rect(proj.location[0], self.height - proj.location[1] - proj.height, proj.width, proj.height)
            
            if not proj.is_persistent:
                for plat in self.platforms:
                    if plat.rect.colliderect(p_rect):
                        proj.active = False
                        if proj in self.projectiles: self.projectiles.remove(proj)
                        break
                if not proj.active: continue

            hit = False
            for char in self.characters:
                if not char.is_alive or char.id == proj.owner_id: continue
                c_rect = char.get_rect()
                cp_rect = pygame.Rect(char.location[0], self.height - char.location[1] - c_rect.height, c_rect.width, c_rect.height)
                if p_rect.colliderect(cp_rect):
                    if not proj.skip_collision_damage: char.take_damage(proj.damage)
                    if not proj.is_persistent:
                        proj.active = False
                        hit = True
                    break
            
            if not hit:
                for plat in self.platforms:
                    if p_rect.colliderect(plat.rect):
                        if not proj.is_persistent:
                            proj.active = False
                            hit = True
                        break
            
            if not proj.active:
                if proj in self.projectiles: self.projectiles.remove(proj)
            elif hit and not proj.is_persistent:
                if proj in self.projectiles: self.projectiles.remove(proj)

        # Weapon pickups
        for weapon in self.weapon_pickups[:]:
            if weapon.is_equipped: continue
            w_rect = weapon.get_pickup_rect(self.height)
            for char in self.characters:
                if not char.is_alive or char.weapon: continue
                c_rect = char.get_rect()
                cp_rect = pygame.Rect(char.location[0], self.height - char.location[1] - c_rect.height, c_rect.width, c_rect.height)
                if cp_rect.colliderect(w_rect):
                    char.pickup_weapon(weapon)
                    weapon.pickup()
                    if weapon in self.weapon_pickups: self.weapon_pickups.remove(weapon)
                    break
        
        # Check for ammo pickups
        for ammo in self.ammo_pickups[:]:
            if not ammo.is_active: continue
            a_rect = ammo.get_pickup_rect(self.height)
            for char in self.characters:
                if not char.is_alive or not char.weapon: continue
                c_rect = char.get_rect()
                cp_rect = pygame.Rect(char.location[0], self.height - char.location[1] - c_rect.height, c_rect.width, c_rect.height)
                if cp_rect.colliderect(a_rect):
                    char.weapon.add_ammo(ammo.ammo_amount)
                    ammo.pickup()
                    if ammo in self.ammo_pickups: self.ammo_pickups.remove(ammo)
                    break

    def spawn_weapon(self, weapon):
        weapon.is_equipped = False
        if weapon not in self.weapon_pickups:
            self.weapon_pickups.append(weapon)

    def spawn_ammo(self, ammo_pickup):
        """Add an ammo pickup to the arena."""
        from BASE_components.BASE_ammo import BaseAmmoPickup
        if isinstance(ammo_pickup, BaseAmmoPickup):
            ammo_pickup.is_active = True
            if ammo_pickup not in self.ammo_pickups:
                self.ammo_pickups.append(ammo_pickup)

    def manage_weapon_spawns(self, delta_time: float):
        self.weapon_spawn_timer += delta_time
        if self.weapon_spawn_timer >= self.spawn_interval:
            self.weapon_spawn_timer = 0.0
            # TODO: implement that it spawns a weapon every time a character dies
            #if self.lootpool and len(self.weapon_pickups) < max(2, len(self.characters)):
            if self.lootpool:
                random.seed(self.spawn_count + 42)
                self.spawn_count += 1
                # Only spawn on platforms wide enough for weapon placement (need at least 40px width)
                valid_platforms = [p for p in self.platforms if p.rect.width >= 40]
                if not valid_platforms:
                    return  # No suitable platforms for spawning
                plat = random.choice(valid_platforms)
                weapon_name = random.choice(list(self.lootpool.keys()))
                weapon = self.lootpool[weapon_name]([random.randint(int(plat.rect.left), int(plat.rect.right-40)), self.height - plat.rect.top])
                self.spawn_weapon(weapon)
    
    def manage_ammo_spawns(self, delta_time: float):
        """Spawn ammo pickups periodically on platforms."""
        from BASE_components.BASE_ammo import BaseAmmoPickup
        
        self.ammo_spawn_timer += delta_time
        if self.ammo_spawn_timer >= self.ammo_spawn_interval:
            self.ammo_spawn_timer = 0.0
            # Limit total ammo pickups (max 2)
            if len(self.ammo_pickups) < 2:
                random.seed(self.ammo_spawn_count + 100)
                self.ammo_spawn_count += 1
                # Only spawn on platforms wide enough
                valid_platforms = [p for p in self.platforms if p.rect.width >= 30]
                if not valid_platforms:
                    return
                plat = random.choice(valid_platforms)
                ammo_amount = random.choice([5, 10, 15])  # Random ammo amounts
                x_pos = random.randint(int(plat.rect.left), int(plat.rect.right - 20))
                y_pos = self.height - plat.rect.top
                ammo = BaseAmmoPickup([x_pos, y_pos], ammo_amount)
                self.spawn_ammo(ammo)

                # Try to spawn mirrored ammo pickup
                mirrored_x = self.width - x_pos
                # Check if there's a valid platform at the mirrored position
                mirrored_platform = None
                for p in self.platforms:
                    if p.rect.left <= mirrored_x <= p.rect.right - 20 and p.rect.width >= 30:
                        mirrored_platform = p
                        break

                # Spawn mirrored ammo if platform exists and we haven't exceeded limit
                if mirrored_platform and len(self.ammo_pickups) < 2:
                    mirrored_ammo = BaseAmmoPickup([mirrored_x, y_pos], ammo_amount)
                    self.spawn_ammo(mirrored_ammo)

    def render(self):
        """Draw everything."""
        if self.headless:
            return  # No rendering in headless mode

        self.screen.fill((135, 206, 235))
        for plat in self.platforms: plat.draw(self.screen)
        for weapon in self.weapon_pickups: weapon.draw(self.screen, self.height)
        for ammo in self.ammo_pickups: ammo.draw(self.screen, self.height)
        for proj in self.projectiles: proj.draw(self.screen, self.height)
        for char in self.characters: char.draw(self.screen, self.height)
        self.ui.draw(self.characters, self.game_over, self.winner, self.respawn_timer)
        pygame.display.flip()

    def step(self):
        """One frame."""
        if self.headless:
            # In headless mode, we don't use pygame clock
            import time
            frame_delta = 1.0 / self.TICK_RATE  # Fixed timestep
        else:
            frame_delta = self.clock.tick(60) / 1000.0

        # Capture input (skip in headless mode)
        if not self.headless:
            self._capture_input()

        # Update game simulation
        self.tick_accumulator += frame_delta
        while self.tick_accumulator >= self.tick_interval:
            self._update_simulation(self.tick_interval)
            self.tick_accumulator -= self.tick_interval

        # Update all characters
        for char in self.characters:
            char.update(frame_delta, self.platforms, self.height)

        self.render()

    def update(self, delta_time: float):
        """
        Update game simulation (physics only, no rendering/input).
        Used by server for headless simulation.
        """
        # Update game simulation
        self.tick_accumulator += delta_time
        while self.tick_accumulator >= self.tick_interval:
            self._update_simulation(self.tick_interval)
            self.tick_accumulator -= self.tick_interval

        # Update all characters
        for char in self.characters:
            char.update(delta_time, self.platforms, self.height, self.width)

    def _capture_input(self):
        """Capture local player input."""
        # Skip pygame event handling in headless mode to avoid main thread issues
        if not self.headless:
            pygame.event.pump()
            mx, my = pygame.mouse.get_pos()
            world_mx, world_my = self.screen_to_world(mx, my)
            pressed = pygame.mouse.get_pressed()

            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self.held_keycodes.add(event.key)
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                elif event.type == pygame.KEYUP:
                    self.held_keycodes.discard(event.key)

            # Process input for the first character (local player) using the new action system
            if self.characters:
                char = self.characters[0]
                if char.is_alive:
                    # Get input data using the character's mapping
                    input_data = char.get_input_data(self.held_keycodes, pressed, [world_mx, world_my])
                    # Process the input data
                    char.process_input(input_data, self)


    def run(self):
        while self.running:
            self.step()
        pygame.quit()
        sys.exit()
