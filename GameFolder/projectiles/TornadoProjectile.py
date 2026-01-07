import pygame
import math
import random
from GameFolder.projectiles.GAME_projectile import Projectile

class TornadoProjectile(Projectile):
    def __init__(self, x, y, direction, damage, owner_id):
        # Tornado is large and moves relatively slowly but consistently
        super().__init__(x, y, direction, speed=3.0, damage=damage, owner_id=owner_id, width=500, height=400)
        self.is_persistent = True
        self.pull_radius = 250 # Maximum pull radius at the top
        self.pull_strength = 4.0
        self.duration = 6.0
        self.timer = 0.0
        self.rotation_angle = 0.0
        # Debris particles for visual effect: (h_ratio, angle, speed, size)
        self.particles = []
        for _ in range(40):
            self.particles.append({
                'h_ratio': random.random(),
                'angle': random.uniform(0, math.pi * 2),
                'speed': random.uniform(2, 5),
                'size': random.randint(2, 5)
            })

    def update(self, delta_time):
        super().update(delta_time)
        self.timer += delta_time
        if self.timer >= self.duration:
            self.active = False
        
        self.rotation_angle += 15.0 * delta_time
        if self.location[1] < 0:
            self.location[1] = 0

    def draw(self, surface, arena_height):
        center_x = self.location[0]
        center_y = arena_height - self.location[1]
        
        num_segments = 20
        for i in range(num_segments):
            h_ratio = i / num_segments
            seg_y = center_y - (h_ratio * self.height)
            seg_width = 2 * self.pull_radius * (0.3 + 0.7 * h_ratio)
            # Swaying intensity: math.sin(self.rotation_angle * 1.5 + h_ratio * 5.0) * 20
            sway = math.sin(self.rotation_angle * 1.5 + h_ratio * 5.0) * 20
            
            # Swirling color palette: light gray and blue-ish gray
            color_shift = math.sin(self.rotation_angle + h_ratio * 10) * 20
            color = (max(0, min(255, 180 + color_shift)), max(0, min(255, 185 + color_shift)), max(0, min(255, 200 + color_shift)))
            
            for offset in [0, math.pi]:
                # Double-spiral effect
                angle = self.rotation_angle * 3.0 + h_ratio * 4.0 + offset
                off_x = math.cos(angle) * (seg_width * 0.2)
                rect = pygame.Rect(0, 0, seg_width, seg_width * 0.25)
                rect.center = (center_x + sway + off_x, seg_y)
                pygame.draw.ellipse(surface, color, rect, 2)

        for p in self.particles:
            h_ratio = p['h_ratio']
            radius_at_h = self.pull_radius * (0.3 + 0.7 * h_ratio)
            orbit_r = radius_at_h * 0.8
            angle = p['angle'] + self.rotation_angle * p['speed'] * 0.2
            dx = math.cos(angle) * orbit_r
            dy = math.sin(angle) * (orbit_r * 0.2)
            sway = math.sin(self.rotation_angle * 1.5 + h_ratio * 5.0) * 20
            p_x = center_x + sway + dx
            p_y = (center_y - h_ratio * self.height) + dy
            pygame.draw.circle(surface, (120, 120, 140), (int(p_x), int(p_y)), p['size'])