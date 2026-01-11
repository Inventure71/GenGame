from GameFolder.weapons.GAME_weapon import Weapon

class Pistol(Weapon):
    """
    A basic pistol weapon with moderate damage and fast cooldown.
    Low damage but reliable for consistent combat.
    """
    def __init__(self, location=None):
        super().__init__(
            name="Pistol",
            damage=10,
            cooldown=0.3,
            projectile_speed=15,
            max_ammo=30,
            ammo_per_shot=1,
            location=location
        )
        # Pistol gets blue color from parent Weapon class
