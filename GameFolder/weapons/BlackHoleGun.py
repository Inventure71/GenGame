import pygame
import time
from GameFolder.weapons.GAME_weapon import Weapon
from GameFolder.projectiles.BlackHoleProjectile import BlackHoleProjectile

class BlackHoleGun(Weapon):
    def __init__(self, location=None):
        super().__init__(
            name="Singularity Cannon",
            damage=0.5,
            cooldown=6.0,
            projectile_speed=400.0,
            max_ammo=5,
            ammo_per_shot=1,
            location=location
        )
        self.color = (75, 0, 130)  # Indigo/Purple

    def shoot(self, owner_x, owner_y, target_x, target_y, owner_id):
        """
        Creates a BlackHoleProjectile targeted at the given coordinates.
        """
        if self.can_shoot():
            # Consume ammo
            self.ammo -= self.ammo_per_shot
            self.last_shot_time = time.time()
            # Create the projectile at the owner's location, aimed at target
            projectile = BlackHoleProjectile(owner_x, owner_y, target_x, target_y, owner_id)
            return [projectile]
        return []