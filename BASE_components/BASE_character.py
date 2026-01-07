import pygame
import uuid
from BASE_components.BASE_weapon import BaseWeapon
from BASE_components.BASE_projectile import BaseProjectile
from BASE_components.network_protocol import CharacterState, char_flags_pack, char_flags_unpack

class BaseCharacter:
    # IMMUTABLE: Life system - all players have exactly 3 lives
    MAX_LIVES = 3

    def __init__(self, name: str, description: str, image: str, location: [float, float], width: float = 50, height: float = 50):
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.image = image
        
        # Dimensions
        self.width = width
        self.height = height

        """Movement"""
        self.location = location # [x, y]
        self.spawn_location = location.copy()  # Store spawn point for respawn
        self.rotation = 0 # 0-360 degrees
        self.scale_ratio = 1.0 
        self.speed = 4.0 # Increased speed
        self.jump_height = 15.0 
        self.gravity = 0.4
        self.vertical_velocity = 0.0
        
        """Movement Flags"""
        self.can_move = True
        self.can_rotate = True
        self.can_jump = True
        self.can_scale = True
        self.can_fly = False
        self.on_ground = False
        self.is_dropping = False # Input flag for dropping through platforms
        self.is_moving_up = False # Input flag for moving up (jumping/flying)
        self.hover_time = 0.0 # current hover time
        self.max_hover_time = 0.0 # max time it can hover for
        
        # Flight Mechanic
        self.max_flight_time = 3.0
        self.flight_time_remaining = self.max_flight_time
        self.needs_recharge = False
        self.is_currently_flying = False
        self.physics_inverted = False # Can be used for status effects
        
        """Combat"""
        self.weapon = None  # No weapon by default - must pick up

        """Life System - IMMUTABLE"""
        self.lives = self.MAX_LIVES  # Cannot be changed by children
        self.is_eliminated = False  # True when all lives are lost

        """Vitals"""
        self.max_health = 100.0
        self.health = 100.0
        self.max_stamina = 100.0
        self.stamina = 100.0
        self.is_alive = True

        """Attributes"""
        self.strength = 10.0
        self.defense = 5.0
        self.agility = 10.0

        """Temporary Modifiers"""
        self.speed_multiplier = 1.0
        self.rotation_multiplier = 1.0
        self.scale_multiplier = 1.0
        self.jump_height_multiplier = 1.0
        self.gravity_multiplier = 1.0
        self.damage_multiplier = 1.0
        self.defense_multiplier = 1.0

    def get_rect(self) -> pygame.Rect:
        # In Pygame, y increases downwards. 
        # For our internal logic (y up), we will flip y in the Arena/Renderer.
        return pygame.Rect(self.location[0], self.location[1], self.width * self.scale_ratio, self.height * self.scale_ratio)

    def shoot(self, target_pos: [float, float]) -> BaseProjectile:
        if not self.is_alive or not self.weapon:
            return None
        
        # Center of character
        start_x = self.location[0] + (self.width * self.scale_ratio) / 2
        start_y = self.location[1] + (self.height * self.scale_ratio) / 2
        
        return self.weapon.shoot(start_x, start_y, target_pos[0], target_pos[1], self.id)

    def secondary_fire(self, target_pos: [float, float]) -> BaseProjectile:
        """Override to implement secondary fire mode"""
        if not self.is_alive or not self.weapon:
            return None
        
        start_x = self.location[0] + (self.width * self.scale_ratio) / 2
        start_y = self.location[1] + (self.height * self.scale_ratio) / 2
        
        if hasattr(self.weapon, 'secondary_fire'):
            return self.weapon.secondary_fire(start_x, start_y, target_pos[0], target_pos[1], self.id)
        return None

    def special_fire(self, target_pos: [float, float], is_holding: bool) -> BaseProjectile:
        """Override to implement special fire/charge mode"""
        if not self.is_alive or not self.weapon:
            return None
            
        start_x = self.location[0] + (self.width * self.scale_ratio) / 2
        start_y = self.location[1] + (self.height * self.scale_ratio) / 2
        
        if hasattr(self.weapon, 'special_fire'):
            return self.weapon.special_fire(start_x, start_y, target_pos[0], target_pos[1], self.id, is_holding)
        return None

    """Movement"""
    def move(self, direction: [float, float], platforms: list = None):
        """
        Move in a 2D direction [x, y].
        y > 0 is up, y < 0 is down.
        """
        if not self.can_move or not self.is_alive:
            return

        # Apply status effects like inverted physics
        actual_dir = [direction[0], direction[1]]
        if self.physics_inverted:
            actual_dir[0] *= -1
            actual_dir[1] *= -1

        # Handle horizontal movement
        self.location[0] += actual_dir[0] * self.speed * self.speed_multiplier

        # Handle vertical movement
        # Update flags
        self.is_dropping = (actual_dir[1] < -0.5)
        self.is_moving_up = (actual_dir[1] > 0)

        # Integrated flight logic
        if not self.on_ground and self.is_moving_up and self.flight_time_remaining > 0 and not self.needs_recharge:
            self.can_fly = True
            self.is_currently_flying = True
        else:
            self.can_fly = False # Reset if not meeting conditions
            self.is_currently_flying = False

        if actual_dir[1] > 0:
            if self.on_ground:
                if self.can_jump:
                    self.jump()
            elif self.can_fly:
                self.location[1] += actual_dir[1] * self.speed * self.speed_multiplier
                self.vertical_velocity = 0
        elif actual_dir[1] < 0:
            if self.can_fly:
                self.location[1] += actual_dir[1] * self.speed * self.speed_multiplier
                self.vertical_velocity = 0 # Cancel gravity
                
                # Prevent going below floor
                if self.location[1] < 0:
                    self.location[1] = 0

    def jump(self):
        if not self.can_jump or not self.is_alive:
            return
        self.vertical_velocity = self.jump_height * self.jump_height_multiplier
        self.on_ground = False

    def hover(self, duration: float):
        if self.max_hover_time <= 0 or not self.is_alive:
            return
        if self.hover_time < self.max_hover_time:
            self.hover_time += duration
            self.vertical_velocity = 0 # stop falling while hovering

    def apply_gravity(self, arena_height: float = 600, platforms: list = None):
        if not self.is_alive:
            return

        if self.can_fly and self.vertical_velocity == 0:
            return

        # Update position based on vertical velocity
        self.location[1] += self.vertical_velocity
        # Apply gravity to velocity
        self.vertical_velocity -= self.gravity * self.gravity_multiplier

        # Check floor
        if self.location[1] <= 0:
            self.location[1] = 0
            self.vertical_velocity = 0
            self.on_ground = True
            self.hover_time = 0
        else:
            self.on_ground = False
            
            # Check platforms
            if platforms and not self.is_dropping and self.vertical_velocity <= 0:
                char_rect = self.get_rect()
                # Feet position in screen coordinates
                py_feet_y = arena_height - self.location[1]
                
                for plat in platforms:
                    # If feet are at or below platform top, but were above it
                    # We use a small buffer (20) to catch fast falling characters
                    overlap = py_feet_y - plat.rect.top
                    if 0 <= overlap < 20:
                        # Horizontal check
                        if self.location[0] + char_rect.width > plat.rect.left and self.location[0] < plat.rect.right:
                            # Land on platform
                            self.location[1] = arena_height - plat.rect.top
                            self.vertical_velocity = 0
                            self.on_ground = True
                            self.hover_time = 0
                            break

    def rotate(self, angle: float): # in degrees
        if not self.can_rotate or not self.is_alive:
            return
        self.rotation = (self.rotation + angle * self.rotation_multiplier) % 360

    def scale(self, scale_delta: float): # 0-100%
        if not self.can_scale or not self.is_alive:
            return
        self.scale_ratio += scale_delta * self.scale_multiplier
        # Keep scale positive
        self.scale_ratio = max(0.1, self.scale_ratio)

    """Vitals & Combat"""
    def take_damage(self, amount: float):
        if not self.is_alive or amount <= 0:
            return
        
        # Simple defense calculation
        reduced_damage = max(1, amount - (self.defense * self.defense_multiplier))
        self.health -= reduced_damage
        
        if self.health <= 0:
            self.health = 0
            self.die()

    def heal(self, amount: float):
        if not self.is_alive:
            return
        self.health = min(self.max_health, self.health + amount)

    def use_stamina(self, amount: float) -> bool:
        if self.stamina >= amount:
            self.stamina -= amount
            return True
        return False

    def regenerate_stamina(self, amount: float):
        if self.is_alive:
            self.stamina = min(self.max_stamina, self.stamina + amount)

    def attack(self, target: 'BaseCharacter'):
        if not self.is_alive:
            return
        
        damage = self.strength * self.damage_multiplier
        target.take_damage(damage)

    def die(self):
        """
        Handle character death.
        """
        self.is_alive = False
        self.lives -= 1
        
        if self.lives > 0:
            print(f"{self.name} has died. Lives remaining: {self.lives}")
        else:
            self.is_eliminated = True
            print(f"{self.name} has been eliminated from the game!")

    def respawn(self, respawn_location: [float, float] = None):
        if self.is_eliminated:
            return
        
        if respawn_location:
            self.location = respawn_location.copy()
        else:
            self.location = self.spawn_location.copy()
        
        # Reset vitals
        self.health = self.max_health
        self.stamina = self.max_stamina
        self.is_alive = True
        self.vertical_velocity = 0.0
        self.on_ground = False
        self.flight_time_remaining = self.max_flight_time
        
        # Drop weapon on death
        self.weapon = None
        
        print(f"{self.name} has respawned!")

    def pickup_weapon(self, weapon):
        if self.weapon is not None:
            return False
        
        self.weapon = weapon
        return True

    def drop_weapon(self):
        dropped_weapon = self.weapon
        self.weapon = None
        return dropped_weapon

    def update(self, delta_time: float, platforms: list = None, arena_height: float = 600):
        """Per-frame update logic"""
        if not self.is_alive:
            return
        
        # Flight recharge logic
        if self.on_ground:
            self.flight_time_remaining = min(self.max_flight_time, self.flight_time_remaining + delta_time * 1.5)
            if self.flight_time_remaining >= self.max_flight_time:
                self.needs_recharge = False
        
        # Fuel consumption
        if self.is_currently_flying and not self.on_ground:
            self.flight_time_remaining -= delta_time
            if self.flight_time_remaining <= 0:
                self.flight_time_remaining = 0
                self.needs_recharge = True
                self.can_fly = False
                self.is_currently_flying = False

        self.apply_gravity(arena_height, platforms)
        self.regenerate_stamina(self.agility * 0.1 * delta_time)

        # Gradually recover multipliers
        recovery_speed = 0.5 * delta_time
        if self.speed_multiplier < 1.0:
            self.speed_multiplier = min(1.0, self.speed_multiplier + recovery_speed)
        elif self.speed_multiplier > 1.0:
            self.speed_multiplier = max(1.0, self.speed_multiplier - recovery_speed)

        if self.jump_height_multiplier < 1.0:
            self.jump_height_multiplier = min(1.0, self.jump_height_multiplier + recovery_speed)
        elif self.jump_height_multiplier > 1.0:
            self.jump_height_multiplier = max(1.0, self.jump_height_multiplier - recovery_speed)

    # =========================================================================
    # NETWORK SYNC
    # =========================================================================

    def get_network_state(self, player_id: int, weapon_id: int) -> CharacterState:
        """Create a state packet for this character."""
        flags = char_flags_pack(
            self.is_alive,
            self.is_eliminated,
            self.on_ground,
            self.is_currently_flying
        )
        return CharacterState(
            player_id=player_id,
            x=self.location[0],
            y=self.location[1],
            vel_y=self.vertical_velocity,
            health=self.health,
            lives=self.lives,
            flags=flags,
            weapon_id=weapon_id
        )

    def apply_network_state(self, state: CharacterState, is_local: bool, weapon_spawner=None):
        """Apply a state packet to this character."""
        # 1. Position & Physics
        if is_local:
            # Drift correction
            dx = abs(self.location[0] - state.x)
            dy = abs(self.location[1] - state.y)
            if dx > 15 or dy > 15:
                self.location[0] = state.x
                self.location[1] = state.y
                self.vertical_velocity = state.vel_y
        else:
            self.location[0] = state.x
            self.location[1] = state.y
            self.vertical_velocity = state.vel_y
        
        # 2. Vitals & Flags
        self.health = state.health
        self.lives = state.lives
        
        was_alive = self.is_alive
        self.is_alive, self.is_eliminated, self.on_ground, is_flying = char_flags_unpack(state.flags)
        self.is_currently_flying = is_flying
        
        # 3. Weapon
        if weapon_spawner and state.weapon_id > 0:
            weapon_spawner(self, state.weapon_id)
        elif state.weapon_id == 0:
            self.weapon = None

    def draw(self, screen: pygame.Surface, arena_height: float):
        if not self.is_alive:
            return
        
        # Map our y-up coordinates to Pygame's y-down coordinates
        py_y = arena_height - self.location[1] - (self.height * self.scale_ratio)
        py_rect = pygame.Rect(self.location[0], py_y, self.width * self.scale_ratio, self.height * self.scale_ratio)
        
        # Attempt to draw image, fallback to rect
        try:
            # This is a placeholder, normally you'd load and cache images
            # image = pygame.image.load(self.image)
            # screen.blit(image, py_rect)
            pygame.draw.rect(screen, (0, 255, 0), py_rect)
        except:
            pygame.draw.rect(screen, (0, 255, 0), py_rect)
        
        # Draw health bar
        health_bar_width = self.width * self.scale_ratio
        health_ratio = self.health / self.max_health
        pygame.draw.rect(screen, (255, 0, 0), (self.location[0], py_y - 10, health_bar_width, 5))
        pygame.draw.rect(screen, (0, 255, 0), (self.location[0], py_y - 10, health_bar_width * health_ratio, 5))
