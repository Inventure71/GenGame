from GameFolder.effects.GAME_effects import RadialEffect


def activate(cow, arena, mouse_pos):
    cow.primary_knockback = 3
    radius = cow.size * 2
    damage = max(0.0, cow.health - 1.0)
    cow.health = 1.0
    cow.size = 9.0
    cow.changed_size()
    cow.primary_delay = 1.0
    effect = RadialEffect(
        location=[cow.location[0], cow.location[1]],
        radius=radius,
        owner_id=cow.id,
        damage=damage,
        damage_cooldown=cow.primary_delay,
        knockback_distance=cow.primary_knockback,
    )
    arena.add_effect(effect)


ABILITY = {
    "name": "Final Moo-ment",
    "description": "Sacrifice your size to unleash a massive, devastating blast.",
    "max_charges": 1,
    "activate": activate,
}
