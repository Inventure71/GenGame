# Guide: Adding New Abilities (Auto-Discovery)

This game auto-discovers abilities from `GameFolder/abilities/primary/` and `GameFolder/abilities/passive/`.
You only need to add a new file with an `ABILITY` dict. No registry edits.

## Step-by-Step: Add a New Primary Ability

1) Create a new file:
   - `GameFolder/abilities/primary/gravity_milkstorm.py`

2) Define a callable `activate(cow, arena, mouse_pos)` and an `ABILITY` dict.
   - **Required keys**: `name`, `description`, `max_charges`, `activate`

Example (intentionally wild, multi-effect):

```python
from GameFolder.effects.radialeffect import RadialEffect
from GameFolder.effects.lineeffect import LineEffect


def activate(cow, arena, mouse_pos):
    # Burst ring damage around the cow
    arena.add_effect(RadialEffect(
        location=[cow.location[0], cow.location[1]],
        radius=160,
        owner_id=cow.id,
        damage=18 * cow.damage_multiplier,
        damage_cooldown=0.6,
        knockback_distance=40,
    ))

    # Beam toward cursor for precision damage
    angle = cow._angle_to_mouse(mouse_pos)
    arena.add_effect(LineEffect(
        location=[cow.location[0], cow.location[1]],
        angle=angle,
        length=260,
        width=10,
        owner_id=cow.id,
        damage=14 * cow.damage_multiplier,
        damage_cooldown=0.3,
        knockback_distance=0,
    ))

    # Tradeoff: shrink slightly after casting
    cow.size = max(9.0, cow.size - 2.5)
    cow.changed_size()


ABILITY = {
    "name": "Gravity Milkstorm",
    "description": "Explodes a heavy milk ring, then fires a beam toward the cursor. Shrinks you slightly.",
    "max_charges": 2,
    "activate": activate,
}
```

3) Save the file. That is it. The loader finds it automatically.

## Step-by-Step: Add a New Passive Ability

1) Create a new file:
   - `GameFolder/abilities/passive/rumble_hooves.py`

2) Define a callable `apply(cow)` and an `ABILITY` dict.
   - **Required keys**: `name`, `description`, `apply`

Example (intentionally wild, multi-effect):

```python

def apply(cow):
    # Speed boost when big
    cow.speed = max(cow.speed, 4.5)
    # Stronger knockback when attacking
    cow.attack_speed_multiplier = max(cow.attack_speed_multiplier, 2.3)
    # Slower dash recharge to balance power
    cow.time_to_recharge_dash = min(2.0, cow.time_to_recharge_dash * 1.5)


ABILITY = {
    "name": "Rumble Hooves",
    "description": "Boosts speed and attack momentum, but slows dash recharge to balance power.",
    "apply": apply,
}
```

3) Save the file. The loader picks it up automatically.

## Notes
- **Description is mandatory**. Missing descriptions raise errors.
- Abilities are discovered at runtime from the folder. No registry file edits.
- Use the concrete effect modules in `GameFolder/effects/` (e.g. `coneeffect`, `radialeffect`, `lineeffect`, `waveprojectileeffect`, `obstacleeffect`, `zoneindicator`) for reusable effect shapes.
- Keep logic inside the ability file as much as possible.