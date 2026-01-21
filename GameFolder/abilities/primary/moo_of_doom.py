from GameFolder.effects.waveprojectileeffect import WaveProjectileEffect


def activate(cow, arena, mouse_pos):
    cow.primary_damage = 60
    cow.primary_delay = 1.0
    angle = cow._angle_to_mouse(mouse_pos)
    effect = WaveProjectileEffect(
        location=[cow.location[0], cow.location[1]],
        angle=angle,
        max_distance=500,
        speed=6,
        owner_id=cow.id,
        damage=cow.primary_damage * cow.damage_multiplier,
    )
    arena.add_effect(effect)


ABILITY = {
    "name": "Moo of Doom",
    "description": "Launch a traveling shockwave that hits anything in its path.",
    "max_charges": 1,
    "activate": activate,
}
