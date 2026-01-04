import math
import time
from GameFolder.weapons.GAME_weapon import Weapon
from GameFolder.projectiles.TornadoProjectile import TornadoProjectile

class TornadoGun(Weapon):
    def __init__(self, location=None):
        # High cooldown because the tornado is very disruptive
        super().__init__("Tornado Launcher", damage=0.8, cooldown=4.0, projectile_speed=150.0, location=location)
        self.color = (180, 180, 180)

    def shoot(self, owner_x, owner_y, target_x, target_y, owner_id):
        if not self.can_shoot():
            return []

        dx = target_x - owner_x
        dy = target_y - owner_y
        dist = math.hypot(dx, dy)
        
        if dist == 0:
            direction = [1, 0]
        else:
            direction = [dx / dist, dy / dist]

        self.last_shot_time = time.time()
        
        # Create the tornado at the owner's position
        return [TornadoProjectile(owner_x, owner_y, direction, self.damage, owner_id)]