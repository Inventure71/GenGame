import pygame
import sys
import random
from BASE_components.BASE_character import BaseCharacter
from BASE_components.BASE_platform import BasePlatform
from BASE_components.BASE_ui import BaseUI

class Arena:
    def __init__(self, width: int = 800, height: int = 600):
        pygame.init()
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("GenGame Arena")
        self.clock = pygame.time.Clock()
        self.running = True
        
        self.characters = []
        self.platforms = []
        self.projectiles = []
        self.weapon_pickups = []  # Weapons on the ground
        
        # Game State
        self.game_over = False
        self.winner = None
        self.respawn_timer = {}  # {character_id: time_remaining}
        self.respawn_delay = 2.0  # seconds before respawn
        
        # UI System
        self.ui = BaseUI(self.screen, self.width, self.height)
        
        # Default Floor platform (Visual only, at y=0)
        # Rect top at self.height ensures it is drawn just below the playable area
        self.platforms.append(BasePlatform(0, self.height, self.width, 20, (50, 50, 50)))

        self.lootpool = {} # Dictionary of { "WeaponName": ClassOrFactory }
        
        # Spawning state
        self.weapon_spawn_timer = 0.0
        self.spawn_interval = 8.0 # Default spawn every 8 seconds
    
    def register_weapon_type(self, name, weapon_provider):
        """
        Registers a weapon into the lootpool. 
        weapon_provider can be a Class or a function that returns a Weapon instance.
        """
        self.lootpool[name] = weapon_provider

    def add_character(self, character: BaseCharacter):
        self.characters.append(character)

    def add_platform(self, platform: BasePlatform):
        self.platforms.append(platform)

    def get_respawn_location(self, character: BaseCharacter) -> [float, float]:
        """
        Get respawn location for a character.
        Default: center top of arena.
        Can be overridden by children for custom spawn points.
        """
        return [self.width / 2, self.height - 100]

    def handle_respawns(self, delta_time: float):
        """
        Handle character respawn timers and respawn dead characters.
        """
        for char in self.characters:
            if not char.is_alive and not char.is_eliminated:
                # Start respawn timer if not already started
                if char.id not in self.respawn_timer:
                    self.respawn_timer[char.id] = self.respawn_delay
                
                # Count down timer
                self.respawn_timer[char.id] -= delta_time
                
                # Respawn when timer reaches 0
                if self.respawn_timer[char.id] <= 0:
                    respawn_loc = self.get_respawn_location(char)
                    char.respawn(respawn_loc)
                    del self.respawn_timer[char.id]

    def check_winner(self):
        """
        Check if there's a winner.
        Winner is determined when only one player has lives remaining.
        """
        if self.game_over:
            return
        
        alive_players = [char for char in self.characters if not char.is_eliminated]
        
        if len(alive_players) == 1:
            self.winner = alive_players[0]
            self.game_over = True
            print(f"\n{'='*50}")
            print(f"GAME OVER! {self.winner.name} WINS!")
            print(f"{'='*50}\n")
        elif len(alive_players) == 0:
            self.game_over = True
            print("Game Over! No winner (draw).")

    def handle_collisions(self, delta_time: float = 0.016):
        # Update and check projectiles
        for proj in self.projectiles[:]:
            proj.update(delta_time)
            
            # Convert proj to pygame coords for collision
            p_py_y = self.height - proj.location[1] - proj.height
            p_py_rect = pygame.Rect(proj.location[0], p_py_y, proj.width, proj.height)

            # Projectile vs Characters
            hit_something = False
            for char in self.characters:
                if not char.is_alive or char.id == proj.owner_id:
                    continue
                
                char_rect = char.get_rect()
                char_py_y = self.height - char.location[1] - char_rect.height
                char_py_rect = pygame.Rect(char.location[0], char_py_y, char_rect.width, char_rect.height)
                
                if p_py_rect.colliderect(char_py_rect):
                    char.take_damage(proj.damage)
                    proj.active = False
                    if proj in self.projectiles:
                        self.projectiles.remove(proj)
                    hit_something = True
                    break
            
            if hit_something:
                continue

            # Projectile vs Platforms
            for plat in self.platforms:
                if p_py_rect.colliderect(plat.rect):
                    proj.active = False
                    if proj in self.projectiles:
                        self.projectiles.remove(proj)
                    hit_something = True
                    break
            
            # Remove off-screen projectiles
            if not hit_something:
                if (proj.location[0] < -100 or proj.location[0] > self.width + 100 or 
                    proj.location[1] < -100 or proj.location[1] > self.height + 100):
                    if proj in self.projectiles:
                        self.projectiles.remove(proj)
        
        # Platform collision detection has been moved to character's update() method
        # which calls apply_gravity() and properly handles on_ground state
        # We no longer need to duplicate that logic here

        # Weapon pickup collisions
        for weapon in self.weapon_pickups[:]:
            if weapon.is_equipped:
                continue
            
            weapon_pickup_rect = weapon.get_pickup_rect(self.height)
            
            for char in self.characters:
                if not char.is_alive:
                    continue
                
                # IMPORTANT: Character can only pick up weapon if they don't already have one
                if char.weapon is not None:
                    continue  # Skip this character, they already have a weapon
                
                char_rect = char.get_rect()
                char_py_y = self.height - char.location[1] - char_rect.height
                char_py_rect = pygame.Rect(char.location[0], char_py_y, char_rect.width, char_rect.height)
                
                if char_py_rect.colliderect(weapon_pickup_rect):
                    # Character picks up weapon (only happens if char.weapon was None)
                    char.pickup_weapon(weapon)
                    weapon.pickup()
                    
                    # Remove picked up weapon from pickups list
                    if weapon in self.weapon_pickups:
                        self.weapon_pickups.remove(weapon)
                    break

    def spawn_weapon(self, weapon):
        """
        Spawn a weapon at its location on the ground.
        """
        weapon.is_equipped = False
        if weapon not in self.weapon_pickups:
            self.weapon_pickups.append(weapon)

    def manage_weapon_spawns(self, delta_time: float):
        """
        Manage weapon spawns - ensure max 1 weapon per player on ground at a time.
        Uses the lootpool to pick random weapons.
        """
        self.weapon_spawn_timer += delta_time
        if self.weapon_spawn_timer >= self.spawn_interval:
            self.weapon_spawn_timer = 0.0
            
            # Limit weapons on ground to number of characters (min 2, max 4)
            max_weapons = max(2, min(4, len(self.characters)))
            active_pickups = len([w for w in self.weapon_pickups if not w.is_equipped])
            
            if self.lootpool and active_pickups < max_weapons:
                # Need platforms to spawn on
                if not self.platforms:
                    return
                
                # Choose a random platform (preferring non-floor platforms if available)
                platforms_to_use = self.platforms[1:] if len(self.platforms) > 1 else self.platforms
                plat = random.choice(platforms_to_use)
                
                # Spawn on top of the platform
                spawn_x = random.randint(int(plat.rect.left), max(int(plat.rect.left), int(plat.rect.right - 40)))
                spawn_y = self.height - plat.rect.top
                
                # Pick a random weapon type from the lootpool
                weapon_name = random.choice(list(self.lootpool.keys()))
                provider = self.lootpool[weapon_name]
                
                # Instantiate (provider is a class or factory function)
                weapon = provider([spawn_x, spawn_y])
                self.spawn_weapon(weapon)

    def run(self):
        while self.running:
            delta_time = self.clock.tick(60) / 1000.0 # seconds
            
            # Manage weapon spawning
            self.manage_weapon_spawns(delta_time)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_q and self.characters:
                        # Drop weapon (Q key) - drop it away from character
                        dropped = self.characters[0].drop_weapon()
                        if dropped:
                            # Drop weapon 80 pixels away (outside pickup radius of 50)
                            drop_location = [
                                self.characters[0].location[0] + 80,
                                self.characters[0].location[1]
                            ]
                            dropped.drop(drop_location)
                            self.spawn_weapon(dropped)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1 and self.characters: # Left click
                        # Convert mouse pos to world coords if needed, or just use screen coords
                        # Pygame mouse is (0,0) top-left.
                        # We need to map to world for the projectile direction logic if we want to aim precisely?
                        # Weapon.shoot takes target_x, target_y.
                        mx, my = pygame.mouse.get_pos()
                        # Map Y down to Y up
                        world_my = self.height - my
                        
                        proj = self.characters[0].shoot([mx, world_my])
                        if proj:
                            if isinstance(proj, list):
                                self.projectiles.extend(proj)
                            else:
                                self.projectiles.append(proj)

            # Update characters first (apply gravity and physics)
            for char in self.characters:
                char.update(delta_time, self.platforms, self.height)
            
            # Handle collisions BEFORE input (so on_ground state is correct)
            self.handle_collisions(delta_time)
            
            # Basic input for the first character (for testing)
            # Process AFTER collisions so on_ground is current for jumping
            if self.characters:
                keys = pygame.key.get_pressed()
                move_dir = [0, 0]
                if keys[pygame.K_LEFT]: move_dir[0] -= 1
                if keys[pygame.K_RIGHT]: move_dir[0] += 1
                if keys[pygame.K_UP]: move_dir[1] += 1 # Jump/Fly
                if keys[pygame.K_DOWN]: move_dir[1] -= 1 # Descent (Fly down)
                
                self.characters[0].move(move_dir, self.platforms)
            
            # Handle respawns and check winner
            self.handle_respawns(delta_time)
            self.check_winner()

            # Draw
            self.screen.fill((135, 206, 235)) # Sky blue
            
            for plat in self.platforms:
                plat.draw(self.screen)
            
            # Draw weapon pickups on ground
            for weapon in self.weapon_pickups:
                weapon.draw(self.screen, self.height)
            
            for proj in self.projectiles:
                proj.draw(self.screen, self.height)
                
            for char in self.characters:
                char.draw(self.screen, self.height)
            
            # Draw UI (on top of everything)
            self.ui.draw(self.characters, self.game_over, self.winner, self.respawn_timer)

            pygame.display.flip()


        pygame.quit()
        sys.exit()

