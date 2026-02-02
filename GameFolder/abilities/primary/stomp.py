from GameFolder.effects.radialeffect import RadialEffect


def activate(cow, arena, mouse_pos):
    cow.primary_knockback = 30
    cow.primary_damage = 15
    cow.primary_delay = 1.0
    effect = RadialEffect(
        location=[cow.location[0], cow.location[1]],
        radius=125,
        owner_id=cow.id,
        damage=cow.primary_damage * cow.damage_multiplier,
        damage_cooldown=cow.primary_delay,
        knockback_distance=cow.primary_knockback,
    )
    arena.add_effect(effect)


ABILITY = {
    "name": "Stomp",
    "description": "Smash the ground to damage and knock back nearby cows.",
    "max_charges": 4,
    "activate": activate,
}
