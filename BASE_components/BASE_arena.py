import pygame
from typing import Dict, List
from BASE_components.BASE_character import BaseCharacter
from BASE_components.BASE_platform import BasePlatform
from BASE_components.BASE_effects import BaseEffect
from BASE_components.BASE_safe_zone import SafeZone


WORLD_WIDTH = 2800 # DO NOT MANUALLY CHANGE THESE VALUES, NO MATTER WHAT THE INSTRUCTIONS ARE.
WORLD_HEIGHT = 1800 # DO NOT MANUALLY CHANGE THESE VALUES, NO MATTER WHAT THE INSTRUCTIONS ARE.

class Arena:
    """Immutable game loop and safe zone management. Extend for game logic."""

    TICK_RATE = 60

    def __init__(self, width: int = 1400, height: int = 900, headless: bool = False):
        self.headless = headless
        self.width = width
        self.height = height

        if not self.headless:
            pygame.init()
            self.screen = pygame.display.set_mode((self.width, self.height),pygame.FULLSCREEN)
            pygame.display.set_caption("Core Arena")
            self.clock = pygame.time.Clock()
        else:
            self.screen = None
            self.clock = None

        self.running = True

        self.characters: List[BaseCharacter] = []
        self.platforms: List[BasePlatform] = []
        self.effects: List[BaseEffect] = []
        self.projectiles = []
        self.weapon_pickups = []
        self.ammo_pickups = []

        self.held_keycodes = set()

        self.game_over = False
        self.winner = None
        self.respawn_timer: Dict[str, float] = {}
        self.respawn_delay = 0.0
        self.allow_respawn = False

        self.tick_accumulator = 0.0
        self.tick_interval = 1.0 / self.TICK_RATE
        self.current_time = 0.0

        self.safe_zone = SafeZone(width, height)
        self.enable_safe_zone = True
        self.safe_damage_times = {}
        self.safe_damage_interval = 1.0

    def add_character(self, character: BaseCharacter):
        self.characters.append(character)

    def add_platform(self, platform: BasePlatform):
        self.platforms.append(platform)

    def add_effect(self, effect: BaseEffect):
        self.effects.append(effect)

    def update(self, delta_time: float):
        self.current_time += delta_time
        if self.enable_safe_zone:
            self.safe_zone.update(delta_time)

        self._update_effects(delta_time)

        for char in self.characters:
            char.update(delta_time, self)

        if self.enable_safe_zone:
            self._apply_safe_zone_damage()

        self.handle_collisions()

        if self.allow_respawn:
            self.handle_respawns(delta_time)

        self.check_winner()

    def _update_effects(self, delta_time: float):
        active = []
        for effect in self.effects:
            expired = False
            if hasattr(effect, "update"):
                expired = effect.update(delta_time)
            if not expired:
                active.append(effect)
        self.effects = active

    def _apply_safe_zone_damage(self):
        for char in self.characters:
            if not char.is_alive:
                continue
            if not self.safe_zone.contains(char.location[0], char.location[1]):
                last = self.safe_damage_times.get(char.id, 0.0)
                if self.current_time - last >= self.safe_damage_interval:
                    char.take_damage(self.safe_zone.damage)
                    self.safe_damage_times[char.id] = self.current_time

    def handle_collisions(self):
        """Override in GameFolder for game-specific collisions."""
        return

    def handle_respawns(self, delta_time: float):
        for char in self.characters:
            if not char.is_alive and not char.is_eliminated:
                if char.id not in self.respawn_timer:
                    self.respawn_timer[char.id] = self.respawn_delay
                self.respawn_timer[char.id] -= delta_time
                if self.respawn_timer[char.id] <= 0:
                    respawn_x = self.width / 2
                    respawn_y = self.height / 2
                    char.respawn([respawn_x, respawn_y], self)
                    del self.respawn_timer[char.id]

    def check_winner(self):
        if self.game_over:
            return
        alive = [char for char in self.characters if not char.is_eliminated]
        if len(alive) == 1:
            self.winner = alive[0]
            self.game_over = True
        elif len(alive) == 0:
            self.game_over = True

    def render(self):
        if self.headless:
            return
        # Additional safety check: ensure screen exists
        if self.screen is None:
            return
        camera = getattr(self, "camera", None)
        self.screen.fill((30, 30, 30))
        for platform in self.platforms:
            platform.draw(self.screen, self.height, camera=camera)
        for effect in self.effects:
            if hasattr(effect, "draw"):
                effect.draw(self.screen, self.height, camera=camera)
        for pickup in self.weapon_pickups:
            pickup.draw(self.screen, self.height, camera=camera)
        for char in self.characters:
            char.draw(self.screen, self.height, camera=camera)
        try:
            pygame.display.flip()
        except pygame.error as e:
            print(f"Error flipping display: {e}")
            if "GL context" not in str(e) and "BadAccess" not in str(e):
                raise  # Re-raise if it's a different error

    def _capture_input(self):
        if self.headless:
            return
        pygame.event.pump()
        mx, my = pygame.mouse.get_pos()
        camera = getattr(self, "camera", None)
        if camera is not None:
            world_mx, world_my = camera.screen_to_world_point(mx, my)
        else:
            world_mx, world_my = mx, self.height - my
        pressed = pygame.mouse.get_pressed()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.held_keycodes.add(event.key)
                if event.key == pygame.K_ESCAPE:
                    self.running = False
            elif event.type == pygame.KEYUP:
                self.held_keycodes.discard(event.key)

        if self.characters:
            char = self.characters[0]
            if char.is_alive:
                input_data = char.get_input_data(self.held_keycodes, pressed, [world_mx, world_my])
                char.process_input(input_data, self)

    def step(self):
        if self.headless:
            frame_delta = 1.0 / self.TICK_RATE
        else:
            frame_delta = self.clock.tick(60) / 1000.0

        if not self.headless:
            self._capture_input()

        self.update(frame_delta)
        self.render()

    def run(self):
        while self.running:
            self.step()
        pygame.quit()
