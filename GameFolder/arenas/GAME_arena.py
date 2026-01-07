from BASE_components.BASE_arena import Arena as BaseArena
from GameFolder.characters.GAME_character import Character
from GameFolder.platforms.GAME_platform import Platform
from GameFolder.ui.GAME_ui import GameUI
from GameFolder.weapons.BlackHoleGun import BlackHoleGun
from GameFolder.weapons.TornadoGun import TornadoGun
from GameFolder.weapons.OrbitalCannon import OrbitalCannon
from GameFolder.projectiles.GAME_projectile import StormCloud
from GameFolder.projectiles.BlackHoleProjectile import BlackHoleProjectile
from GameFolder.projectiles.TornadoProjectile import TornadoProjectile
from GameFolder.projectiles.OrbitalProjectiles import TargetingLaser, OrbitalStrikeMarker, OrbitalBlast
from BASE_components.BASE_projectile import BaseProjectile
import pygame
import random


class Arena(BaseArena):
    def __init__(self, width: int = 800, height: int = 600, headless: bool = False):
        super().__init__(width, height, headless)
        # Register custom weapons
        self.register_weapon_type("BlackHoleGun", BlackHoleGun)
        self.register_weapon_type("TornadoGun", TornadoGun)
        self.register_weapon_type("OrbitalCannon", OrbitalCannon)
        
        # Register projectile types for binary serialization
        self.register_projectile_type(StormCloud)
        self.register_projectile_type(BlackHoleProjectile)
        self.register_projectile_type(TornadoProjectile)
        self.register_projectile_type(TargetingLaser)
        self.register_projectile_type(OrbitalStrikeMarker)
        self.register_projectile_type(OrbitalBlast)
        
        if not self.headless:
            pygame.display.set_caption(f"GenGame - Battle Arena")
            self.ui = GameUI(self.screen, self.width, self.height)
        else:
            self.ui = None

    def update_world(self, delta_time: float):
        """Update the world simulation (alias for update method for test compatibility)."""
        self.update(delta_time)



    def handle_collisions(self, delta_time: float = 0.016):
        """
        Custom collision logic for special projectiles.
        """
        # 1. Capture special projectiles BEFORE base collision logic removes inactive ones
        special_projs = [p for p in self.projectiles if isinstance(p, (
            BlackHoleProjectile, TornadoProjectile, TargetingLaser,
            OrbitalStrikeMarker, OrbitalBlast, StormCloud
        ))]

        # 2. Call base collisions for standard projectiles and weapon pickups
        super().handle_collisions(delta_time)
        
        # 3. Handle persistent/special projectiles logic
        for plat in self.platforms:
            if hasattr(plat, 'being_pulled'):
                plat.being_pulled = False

        for proj in special_projs:
            # Laser precision collision (clipline)
            if isinstance(proj, TargetingLaser) and proj.active:
                old_pos = (proj.last_location[0], self.height - proj.last_location[1])
                new_pos = (proj.location[0], self.height - proj.location[1])
                hit = False
                
                # Check platforms
                for plat in self.platforms:
                    res = plat.rect.clipline(old_pos, new_pos)
                    if res:
                        hit = True
                        proj.location = [res[0][0], self.height - res[0][1]]
                        break
                
                # Check characters
                if not hit:
                    for char in self.characters:
                        if not char.is_alive or char.id == proj.owner_id:
                            continue
                        c_rect = char.get_rect()
                        char_rect = pygame.Rect(char.location[0], self.height - char.location[1] - c_rect.height, c_rect.width, c_rect.height)
                        res = char_rect.clipline(old_pos, new_pos)
                        if res:
                            hit = True
                            proj.location = [res[0][0], self.height - res[0][1]]
                            break
                
                if hit:
                    proj.active = False
                    # Create marker
                    marker = OrbitalStrikeMarker(proj.location[0], proj.location[1], proj.owner_id)
                    self.projectiles.append(marker)

            # Storm logic
            elif isinstance(proj, StormCloud) and getattr(proj, 'is_raining', False):
                for char in self.characters:
                    if not char.is_alive or char.id == proj.owner_id:
                        continue
                    char_w = char.width * char.scale_ratio
                    if char.location[0] < proj.location[0] + proj.width and char.location[0] + char_w > proj.location[0]:
                        if char.location[1] < proj.location[1]:
                            if random.random() < 0.1:
                                char.take_damage(proj.damage * 40)
                            char.speed_multiplier = 0.4
            
            # Black Hole logic
            elif isinstance(proj, BlackHoleProjectile):
                if not proj.is_stationary:
                    p_rect = pygame.Rect(proj.location[0] - proj.width/2, self.height - proj.location[1] - proj.height/2, proj.width, proj.height + 2)
                    for plat in self.platforms:
                        if p_rect.colliderect(plat.rect):
                            proj.is_stationary = True
                            break

                if proj.is_stationary:
                    for plat in self.platforms[1:]:  # Skip floor
                        dx = proj.location[0] - plat.rect.centerx
                        dy = (self.height - proj.location[1]) - plat.rect.centery
                        dist = (dx**2 + dy**2)**0.5
                        if 0 < dist < proj.pull_radius:
                            if hasattr(plat, 'move'):
                                plat.move((dx/dist)*proj.pull_strength*0.3, (dy/dist)*proj.pull_strength*0.3)
                                plat.being_pulled = True

                    for char in self.characters:
                        if not char.is_alive or char.id == proj.owner_id:
                            continue
                        dx = proj.location[0] - char.location[0]
                        dy = proj.location[1] - char.location[1]
                        dist = (dx**2 + dy**2)**0.5
                        if dist < proj.pull_radius:
                            char.location[0] += (dx/dist)*proj.pull_strength if dist > 0 else 0
                            char.location[1] += (dy/dist)*proj.pull_strength if dist > 0 else 0
                            if dist < 50:
                                char.take_damage(proj.damage * delta_time * 60)
            
            # Tornado logic
            elif isinstance(proj, TornadoProjectile):
                for char in self.characters:
                    if not char.is_alive or char.id == proj.owner_id:
                        continue
                    h_diff = char.location[1] - proj.location[1]
                    if 0 <= h_diff <= proj.height + 50:
                        rad = proj.pull_radius * (0.3 + 0.7 * (min(h_diff, proj.height) / proj.height))
                        char_w = char.width * char.scale_ratio
                        if abs(proj.location[0] - (char.location[0] + char_w/2)) < rad:
                            char.location[0] += (1.0 if char.location[0] < proj.location[0] else -1.0) * proj.pull_strength
                            char.location[1] += proj.pull_strength * 0.8
                            char.take_damage(proj.damage * delta_time * 60)

                for weapon in self.weapon_pickups:
                    if weapon.is_equipped:
                        continue
                    h_diff = weapon.location[1] - proj.location[1]
                    if 0 <= h_diff <= proj.height + 50:
                        rad = proj.pull_radius * (0.3 + 0.7 * (min(h_diff, proj.height) / proj.height))
                        if abs(proj.location[0] - (weapon.location[0] + weapon.width/2)) < rad:
                            weapon.location[0] += (1.0 if weapon.location[0] < proj.location[0] else -1.0) * proj.pull_strength
                            weapon.location[1] += proj.pull_strength * 0.8

                for plat in self.platforms[1:]:  # Skip floor
                    plat_world_y = self.height - plat.rect.bottom
                    h_diff = plat_world_y - proj.location[1]
                    if 0 <= h_diff <= proj.height + 50:
                        rad = proj.pull_radius * (0.3 + 0.7 * (min(h_diff, proj.height) / proj.height))
                        if abs(proj.location[0] - plat.rect.centerx) < rad:
                            plat.being_pulled = True
                            plat.move((1.0 if plat.rect.centerx < proj.location[0] else -1.0) * proj.pull_strength * 0.5, -proj.pull_strength * 0.4)

            # Orbital Blast damage
            elif isinstance(proj, OrbitalBlast):
                for char in self.characters:
                    if not char.is_alive or char.id == proj.owner_id:
                        continue
                    beam_x_min = proj.location[0] - 50
                    beam_x_max = proj.location[0] + 50
                    char_w = char.width * char.scale_ratio
                    if char.location[0] < beam_x_max and char.location[0] + char_w > beam_x_min:
                        char.take_damage(proj.damage * delta_time)

        for plat in self.platforms[1:]:
            if hasattr(plat, 'return_to_origin') and not getattr(plat, 'being_pulled', False):
                plat.return_to_origin(delta_time)