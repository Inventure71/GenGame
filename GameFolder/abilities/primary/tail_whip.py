from GameFolder.effects.GAME_effects import LineEffect


def activate(cow, arena, mouse_pos):
    cow.primary_knockback = 300
    cow.primary_damage = 10
    cow.primary_delay = 0.5
    angle = cow._angle_to_mouse(mouse_pos)
    effect = LineEffect(
        location=[cow.location[0], cow.location[1]],
        angle=angle,
        length=200,
        width=12,
        owner_id=cow.id,
        damage=cow.primary_damage * cow.damage_multiplier,
        damage_cooldown=cow.primary_delay,
        knockback_distance=cow.primary_knockback,
    )
    arena.add_effect(effect)


ABILITY = {
    "name": "Tail Whip",
    "description": "Slash a long line in front of you that damages and knocks back foes.",
    "max_charges": 3,
    "activate": activate,
}
