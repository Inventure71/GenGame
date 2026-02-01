from GameFolder.effects.coneeffect import ConeEffect


def activate(cow, arena, mouse_pos):
    cow.primary_damage = 10
    cow.primary_delay = 0.5
    angle = cow._angle_to_mouse(mouse_pos)
    effect = ConeEffect(
        location=[cow.location[0], cow.location[1]],
        angle=angle,
        height=180,
        base=40,
        owner_id=cow.id,
        damage=cow.primary_damage * cow.damage_multiplier,
        damage_cooldown=cow.primary_delay,
    )
    arena.add_effect(effect)


ABILITY = {
    "name": "Milk Splash",
    "description": "Spray a cone of milk that slows and damages cows in front of you.",
    "max_charges": 4,
    "activate": activate,
}
