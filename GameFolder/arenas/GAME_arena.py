from BASE_components.BASE_arena import Arena as BaseArena
from GameFolder.characters.GAME_character import Character
from GameFolder.platforms.GAME_platform import Platform
from GameFolder.ui.GAME_ui import GameUI
from GameFolder.weapons.GAME_weapon import Weapon, StormBringer
from GameFolder.weapons.BlackHoleGun import BlackHoleGun
from GameFolder.weapons.TornadoGun import TornadoGun
from GameFolder.projectiles.GAME_projectile import StormCloud, Projectile
from GameFolder.projectiles.BlackHoleProjectile import BlackHoleProjectile
from GameFolder.projectiles.TornadoProjectile import TornadoProjectile
from GameFolder.weapons.OrbitalCannon import OrbitalCannon
from GameFolder.projectiles.OrbitalProjectiles import TargetingLaser, OrbitalStrikeMarker, OrbitalBlast
import pygame
import random
import math

class Arena(BaseArena):
    def __init__(self, width: int = 800, height: int = 600):
        super().__init__(width, height)
        # Replace floor platform with custom Platform to support movement
        if self.platforms:
            floor = self.platforms[0]
            self.platforms[0] = Platform(floor.rect.x, floor.rect.y, floor.rect.width, floor.rect.height, floor.color)
            
        # Register custom weapons
        self.register_weapon_type("BlackHoleGun", BlackHoleGun)
        self.register_weapon_type("TornadoGun", TornadoGun)
        self.register_weapon_type("OrbitalCannon", OrbitalCannon)
        
        # Custom aesthetics
        pygame.display.set_caption("GenGame - Battle Arena")
        self.sky_color = (100, 150, 255)
        
        # Use custom UI
        self.ui = GameUI(self.screen, self.width, self.height)

    def handle_collisions(self, delta_time: float = 0.016):
        """
        Custom collision logic for special projectiles.
        Separates persistent projectiles from standard ones to prevent early removal.
        """
        special_projs = []
        standard_projs = []
        
        for plat in self.platforms:
            plat.being_pulled = False

        for p in self.projectiles:
            # Persistent and phase projectiles
            if isinstance(p, (BlackHoleProjectile, TornadoProjectile, TargetingLaser, OrbitalStrikeMarker, OrbitalBlast)):
                special_projs.append(p)
            elif isinstance(p, StormCloud) and p.is_raining:
                special_projs.append(p)
            else:
                standard_projs.append(p)

        
        # Standard collision logic
        self.projectiles = standard_projs
        super().handle_collisions(delta_time)
        
        # Manually handle special/persistent projectiles
        for proj in special_projs:
            # Special case for OrbitalStrikeMarker: check transition even if inactive at start of loop
            if isinstance(proj, OrbitalStrikeMarker) and not proj.active:
                blast = OrbitalBlast(proj.location[0], proj.owner_id)
                if blast not in self.projectiles:
                    self.projectiles.append(blast)
                continue

            if not proj.active:
                continue
                
            proj.update(delta_time)

            # Check if OrbitalStrikeMarker became inactive during update
            if isinstance(proj, OrbitalStrikeMarker) and not proj.active:
                blast = OrbitalBlast(proj.location[0], proj.owner_id)
                if blast not in self.projectiles:
                    self.projectiles.append(blast)
                continue

            if isinstance(proj, StormCloud):
                for char in self.characters:
                    if not char.is_alive or char.id == proj.owner_id: continue
                    
                    char_width = char.width * char.scale_ratio
                    if (char.location[0] < proj.location[0] + proj.width and 
                        char.location[0] + char_width > proj.location[0]):
                        if char.location[1] < proj.location[1]:
                            if random.random() < 0.1:
                                char.take_damage(proj.damage * 40)
                            char.speed_multiplier = 0.4
            
            elif isinstance(proj, BlackHoleProjectile):
                if not proj.is_stationary:
                    # Check for collisions with platforms to trigger stationary mode
                    p_py_x = proj.location[0] - proj.width / 2
                    p_py_y = (self.height - proj.location[1]) - proj.height / 2
                    p_py_rect = pygame.Rect(p_py_x, p_py_y, proj.width, proj.height + 2)
                    for plat in self.platforms:
                        if p_py_rect.colliderect(plat.rect):
                            proj.is_stationary = True
                            break

                if proj.is_stationary:
                    # Pull platforms (skip floor at index 0)
                    for plat in self.platforms[1:]:
                        bh_screen_x = proj.location[0]
                        bh_screen_y = self.height - proj.location[1]
                        
                        dx = bh_screen_x - plat.rect.centerx
                        dy = bh_screen_y - plat.rect.centery
                        dist = (dx**2 + dy**2)**0.5
                        
                        if 0 < dist < proj.pull_radius:
                            force_mult = proj.pull_strength * 0.3
                            force_x = (dx / dist) * force_mult
                            force_y = (dy / dist) * force_mult
                            plat.move(force_x, force_y)
                            plat.being_pulled = True

                    for char in self.characters:
                        if not char.is_alive or char.id == proj.owner_id:
                            continue
                        
                        dx = proj.location[0] - char.location[0]
                        dy = proj.location[1] - char.location[1]
                        dist = (dx**2 + dy**2)**0.5
                        
                        if dist < proj.pull_radius:
                            # Pull direction vector
                            pull_dir_x = dx / dist if dist > 0 else 0
                            pull_dir_y = dy / dist if dist > 0 else 0
                            
                            # Apply pull force
                            char.location[0] += pull_dir_x * proj.pull_strength
                            char.location[1] += pull_dir_y * proj.pull_strength
                            
                            # Close-range damage
                            if dist < 50:
                                char.take_damage(proj.damage * delta_time * 60)
            
            
            elif isinstance(proj, TornadoProjectile):
                # Conical pull logic: wider at top, pulls characters, weapons, and platforms
                for char in self.characters:
                    if not char.is_alive or char.id == proj.owner_id:
                        continue

                    h_diff = char.location[1] - proj.location[1]
                    if 0 <= h_diff <= proj.height + 50:
                        radius_at_h = proj.pull_radius * (0.3 + 0.7 * (min(h_diff, proj.height) / proj.height))
                        char_width = char.width * char.scale_ratio
                        dist_x = abs(proj.location[0] - (char.location[0] + char_width / 2))
                        if dist_x < radius_at_h:
                            # Pull horizontally and lift
                            pull_dir = 1.0 if char.location[0] < proj.location[0] else -1.0
                            char.location[0] += pull_dir * proj.pull_strength
                            char.location[1] += proj.pull_strength * 0.8
                            char.take_damage(proj.damage * delta_time * 60)

                for weapon in self.weapon_pickups:
                    h_diff = weapon.location[1] - proj.location[1]
                    if 0 <= h_diff <= proj.height + 50:
                        radius_at_h = proj.pull_radius * (0.3 + 0.7 * (min(h_diff, proj.height) / proj.height))
                        dist_x = abs(proj.location[0] - (weapon.location[0] + weapon.width / 2))
                        if dist_x < radius_at_h:
                            pull_dir = 1.0 if weapon.location[0] < proj.location[0] else -1.0
                            weapon.location[0] += pull_dir * proj.pull_strength
                            weapon.location[1] += proj.pull_strength * 0.8

                for plat in self.platforms[1:]:
                    # Platform world-y (bottom)
                    plat_world_y = self.height - plat.rect.bottom
                    h_diff = plat_world_y - proj.location[1]
                    if 0 <= h_diff <= proj.height + 50:
                        radius_at_h = proj.pull_radius * (0.3 + 0.7 * (min(h_diff, proj.height) / proj.height))
                        # For platforms, check centerx vs projectile center
                        dist_x = abs(proj.location[0] - plat.rect.centerx)
                        if dist_x < radius_at_h:
                            plat.being_pulled = True
                            pull_dir = 1.0 if plat.rect.centerx < proj.location[0] else -1.0
                            plat.move(pull_dir * proj.pull_strength * 0.5, -proj.pull_strength * 0.4)



            elif isinstance(proj, TargetingLaser):
                # Segment-based collision check to handle high velocity
                old_pos = (proj.last_location[0], self.height - proj.last_location[1])
                new_pos = (proj.location[0], self.height - proj.location[1])
                hit = False
                
                # Platforms
                for plat in self.platforms:
                    res = plat.rect.clipline(old_pos, new_pos)
                    if res:
                        hit = True
                        hit_pos = res[0]
                        proj.location = [hit_pos[0], self.height - hit_pos[1]]
                        break
                
                # Characters (except owner)
                if not hit:
                    for char in self.characters:
                        if not char.is_alive or char.id == proj.owner_id: continue
                        char_w, char_h = char.width * char.scale_ratio, char.height * char.scale_ratio
                        char_rect = pygame.Rect(char.location[0], self.height - char.location[1] - char_h, char_w, char_h)
                        res = char_rect.clipline(old_pos, new_pos)
                        if res:
                            hit = True
                            hit_pos = res[0]
                            proj.location = [hit_pos[0], self.height - hit_pos[1]]
                            break
                
                if hit or not proj.active:
                    marker = OrbitalStrikeMarker(proj.location[0], proj.location[1], proj.owner_id)
                    self.projectiles.append(marker)
                    proj.active = False

            elif isinstance(proj, OrbitalBlast):
                for char in self.characters:
                    if not char.is_alive or char.id == proj.owner_id: continue
                    beam_x_min = proj.location[0] - 50
                    beam_x_max = proj.location[0] + 50
                    char_w = char.width * char.scale_ratio
                    if char.location[0] < beam_x_max and char.location[0] + char_w > beam_x_min:
                        char.take_damage(proj.damage * delta_time)
            
            # Put persistent projectile back into active list
            if proj.active:
                self.projectiles.append(proj)
            
            # Remove off-screen special projectiles (just in case)
            if (proj.location[0] < -200 or proj.location[0] > self.width + 200 or 
                proj.location[1] < -200 or proj.location[1] > self.height + 200):
                if proj in self.projectiles:
                    self.projectiles.remove(proj)

        for plat in self.platforms[1:]: # Skip floor
            if not getattr(plat, 'being_pulled', False):
                plat.return_to_origin(delta_time)

    def run(self):
        """
        Override run to use custom sky color and drawing.
        """
        while self.running:
            delta_time = self.clock.tick(60) / 1000.0
            
            # Base spawning logic
            self.manage_weapon_spawns(delta_time)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_q and self.characters:
                        dropped = self.characters[0].drop_weapon()
                        if dropped:
                            drop_location = [self.characters[0].location[0] + 80, self.characters[0].location[1]]
                            dropped.drop(drop_location)
                            self.spawn_weapon(dropped)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if self.characters:
                        mx, my = pygame.mouse.get_pos()
                        world_my = self.height - my
                        projs = None
                        if event.button == 1:
                            projs = self.characters[0].shoot([mx, world_my])
                        elif event.button == 3:
                            projs = self.characters[0].secondary_fire([mx, world_my])
                        
                        if projs:
                            if isinstance(projs, list): self.projectiles.extend(projs)
                            else: self.projectiles.append(projs)

            # Update characters
            for char in self.characters[:]:
                char.update(delta_time, self.platforms, self.height)

            # Handle collisions
            self.handle_collisions(delta_time)
            
            # Input
            if self.characters:
                keys = pygame.key.get_pressed()
                mx, my = pygame.mouse.get_pos()
                world_my = self.height - my
                
                # Special Fire (Channeled)
                rift_projs = self.characters[0].special_fire([mx, world_my], is_holding=(keys[pygame.K_e] or keys[pygame.K_f]))
                if rift_projs:
                    if isinstance(rift_projs, list): self.projectiles.extend(rift_projs)
                    else: self.projectiles.append(rift_projs)
                
                move_dir = [0, 0]
                if keys[pygame.K_LEFT] or keys[pygame.K_a]: move_dir[0] -= 1
                if keys[pygame.K_RIGHT] or keys[pygame.K_d]: move_dir[0] += 1
                if keys[pygame.K_UP] or keys[pygame.K_w]: move_dir[1] += 1
                if keys[pygame.K_DOWN] or keys[pygame.K_s]: move_dir[1] -= 1
                self.characters[0].move(move_dir, self.platforms)
            
            self.handle_respawns(delta_time)
            self.check_winner()

            # DRAWING
            self.screen.fill(self.sky_color)
            for plat in self.platforms: plat.draw(self.screen)
            for weapon in self.weapon_pickups: weapon.draw(self.screen, self.height)
            for proj in self.projectiles: proj.draw(self.screen, self.height)
            for char in self.characters: char.draw(self.screen, self.height)
            self.ui.draw(self.characters, self.game_over, self.winner, self.respawn_timer)
            pygame.display.flip()

        pygame.quit()