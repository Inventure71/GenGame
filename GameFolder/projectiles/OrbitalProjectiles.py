from GameFolder.projectiles.GAME_projectile import Projectile
import pygame
import math
import random

class TargetingLaser(Projectile):
    def __init__(self, x, y, direction, owner_id, max_dist):
        super().__init__(x, y, direction, speed=1200, damage=5, owner_id=owner_id, width=6, height=6)
        self.color = (255, 0, 0) # Red
        self.start_location = [x, y]
        self.last_location = [x, y]
        self.max_dist = max_dist
        self.dist_traveled = 0

    def update(self, delta_time):
        self.last_location = list(self.location)
        # Manually update location using pixels-per-second instead of base class's pixels-per-frame
        self.location[0] += self.direction[0] * self.speed * delta_time
        self.location[1] += self.direction[1] * self.speed * delta_time

        self.dist_traveled += self.speed * delta_time
        if self.dist_traveled >= self.max_dist and self.active:
            self.active = False


    def draw(self, screen, arena_height):
        if not self.active:
            return

        # Calculate screen coordinates for self.start_location and self.location
        start_screen_x = int(self.start_location[0])
        start_screen_y = int(arena_height - self.start_location[1])
        current_screen_x = int(self.location[0])
        current_screen_y = int(arena_height - self.location[1])

        # Draw a red line from start to current position
        pygame.draw.line(screen, (255, 0, 0), (start_screen_x, start_screen_y), (current_screen_x, current_screen_y), 2)

        # Draw a small bright flare at the current position
        pygame.draw.circle(screen, (255, 200, 200), (current_screen_x, current_screen_y), 4)

class OrbitalStrikeMarker(Projectile):
    def __init__(self, x, y, owner_id):
        # Speed 0, damage 0, width 100, height 20
        super().__init__(x, y, [0, 0], speed=0, damage=0, owner_id=owner_id, width=100, height=20)
        self.warmup_timer = 0.0
        self.warmup_duration = 1.0

    def update(self, delta_time):
        self.warmup_timer += delta_time
        if self.warmup_timer >= self.warmup_duration:
            if self.active:
                self.active = False
        # No need to call super().update() as speed is 0

    def draw(self, screen, arena_height):
        if not self.active:
            return

        # Center the marker horizontally on its x position
        draw_x = self.location[0] - self.width / 2
        py_y = arena_height - self.location[1] - self.height
        
        # Pulsing effect for the red circle
        pulse = (math.sin(self.warmup_timer * 15) + 1) / 2  # 0 to 1
        radius = 20 + 30 * pulse
        center_x = self.location[0]
        center_y = arena_height - self.location[1]
        
        # Draw pulsing red circle
        pygame.draw.circle(screen, (255, 0, 0), (int(center_x), int(center_y)), int(radius), 3)
        
        # Draw faint red vertical line to the top of the screen
        # Use a Surface with alpha for transparency
        # Glow line (thicker, lower alpha)
        glow_surface = pygame.Surface((4, arena_height), pygame.SRCALPHA)
        glow_surface.fill((255, 0, 0, 50))
        screen.blit(glow_surface, (int(center_x) - 2, 0))

        line_surface = pygame.Surface((2, arena_height), pygame.SRCALPHA)
        line_surface.fill((255, 0, 0, 180)) # More visible red
        screen.blit(line_surface, (int(center_x) - 1, 0))

class OrbitalBlast(Projectile):
    def __init__(self, x, owner_id):
        # location [x, 0], speed 0, damage 100 per sec, width 100, height 2000
        super().__init__(x, 0, [0, 1], speed=0, damage=800, owner_id=owner_id, width=100, height=2000)
        self.duration = 0.6
        self.timer = 0.0

    def update(self, delta_time):
        self.timer += delta_time
        if self.timer >= self.duration:
            self.active = False

    def draw(self, screen, arena_height):
        if not self.active:
            return

        center_x = self.location[0]
        
        # Massive white/light-blue beam spanning the entire screen height
        # Glow effect with multiple rectangles
        widths = [100, 80, 40, 20]
        alphas = [50, 100, 180, 255]
        colors = [(255, 50, 50), (255, 100, 50), (255, 150, 50), (255, 200, 50)]
        
        for i in range(len(widths)):
            w = widths[i]
            alpha = alphas[i]
            color = colors[i]
            
            # Flicker effect: modulate alpha
            flicker_alpha = max(0, min(255, alpha + random.randint(-50, 50)))

            beam_surface = pygame.Surface((w, arena_height), pygame.SRCALPHA)
            beam_surface.fill((*color, flicker_alpha))
            screen.blit(beam_surface, (int(center_x - w/2), 0))