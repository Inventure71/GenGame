
def activate(cow, arena, mouse_pos):
    cow.primary_damage = 30
    cow.primary_delay = 1.0
    cow.is_attacking = True
    cow.horn_charge_end_time = arena.current_time + cow.horn_charge_duration


ABILITY = {
    "name": "Horn Charge",
    "description": "Charge toward the cursor, ramming enemies for heavy contact damage.",
    "max_charges": 1,
    "activate": activate,
}
