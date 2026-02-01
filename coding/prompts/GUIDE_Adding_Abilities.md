# Guide: Adding New Abilities (Auto-Discovery)

This game auto-discovers abilities from `GameFolder/abilities/primary/` and `GameFolder/abilities/passive/`.
You only need to add a new file with an `ABILITY` dict. No registry edits.

## Step-by-Step: Add a New Primary Ability

1) Create a new file:
   - `GameFolder/abilities/primary/gravity_milkstorm.py`

2) Define a callable `activate(cow, arena, mouse_pos)` and an `ABILITY` dict.
   - **Required keys**: `name`, `description`, `max_charges`, `activate`
   - If the ability has an ultimate, also define `ultimate(cow, arena, mouse_pos)` and add **`ultimate`** to the `ABILITY` dict.
   - Use the **exact display name** that tests and the pickup system expect (e.g. spelling and punctuation; avoid mismatches like hyphen vs space).
   - When spawning effects, use **`arena.add_effect(effect)`** only—do not append to `arena.effects` directly.

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
    # "ultimate": ultimate,  # add if this ability has an ultimate
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
- **Primary abilities**: The character code expects `ABILITY["activate"]` (and optionally `ABILITY["ultimate"]`). Omit neither if the ability has an ultimate—include both keys.
- **Display name**: Must match exactly what tests and discoverability use (e.g. no hyphen/space mismatch).
- Abilities are discovered at runtime from the folder. No registry file edits.
- Use the concrete effect modules in `GameFolder/effects/` (e.g. `coneeffect`, `radialeffect`, `lineeffect`, `waveprojectileeffect`, `obstacleeffect`, `zoneindicator`) for reusable effect shapes.
- Spawn effects only with **`arena.add_effect(effect)`**.
- Keep logic inside the ability file as much as possible.

## Effect Collision Detection

**CRITICAL**: All effect collision detection accounts for cow size/radius, not just center points. **All interaction detection MUST use the `arena.spatial_grid` for high performance.**

The arena automatically handles collision detection using spatial partitioning:
- **Spatial Optimization**: The arena uses a `SpatialGrid` to narrow down checks. Only objects returned by `spatial_grid.get_nearby()` are considered.
- **Physics vs. Interaction**:
  - **Standard Obstacles**: Only collide with objects where `obstacle_type == 'blocking'`.
  - **Interactive Objects**: Grass, Pickups, and non-blocking Effects are added to the grid but do NOT trigger rigid body collisions.
- **Geometric Shapes**:
  - **RadialEffect**: Uses `_circle_intersects_circle()`
  - **ConeEffect**: Uses `_circle_intersects_triangle()`
  - **LineEffect**: Uses `_circle_intersects_line()`
  - **WaveProjectileEffect**: Uses `rect.colliderect()`

**Why this matters**: Full-map iteration (e.g., `for obj in self.all_objects:`) is prohibited in high-frequency loops. Always use the `spatial_grid` to query for nearby entities.

## Arena Collision: Subclass-Before-Base (CRITICAL)

When you add a **new effect that is a subclass of an existing effect** (e.g. `StardustSundaeEffect` extends `ObstacleEffect`):

- In `GameFolder/arenas/GAME_arena.py`, inside `_resolve_nearby_collisions` (or equivalent), **check the subclass type BEFORE the base type** in the same loop.
- If you check `ObstacleEffect` first, then `StardustSundaeEffect`, every StardustSundae will match the ObstacleEffect branch and subclass-specific logic (e.g. 35 damage, special removal) will never run.
- **Correct order**: `if isinstance(obj, StardustSundaeEffect): ... elif isinstance(obj, ObstacleEffect): ...`
- **Wrong order**: `if isinstance(obj, ObstacleEffect): ... elif isinstance(obj, StardustSundaeEffect): ...` (second branch is unreachable for StardustSundae).

Always add a dedicated branch for the new subclass **above** the branch for its base class.

## Headless / Test Safety

- Tests run with `setup_battle_arena(headless=True)`. No display is created.
- Do **not** add code in `Character.__init__` or in code paths used at character creation (e.g. `AssetHandler.get_random_variant`) that **require** pygame display or a non-headless environment. If asset loading can run headless (e.g. no `pygame.display.get_surface()`), keep it that way.

## Network Serialization Requirements (CRITICAL)

**All effects are network-serializable and sent from server to client.** When creating effects, you MUST follow these rules:

### ❌ NEVER Store Complex Objects
- **DO NOT** store `Character` objects (e.g., `self.cow = cow`)
- **DO NOT** store `Arena` objects (e.g., `self.arena = arena`)
- **DO NOT** store any non-serializable objects

### ✅ DO Store Primitive Data Only
- Store `owner_id` (string) instead of the character object: `self.owner_id = cow.id`
- Store derived values if needed for drawing: `self.cow_size = cow.size`
- Store primitive types: strings, numbers, lists, tuples, dicts

### ✅ Keep Effects Self-Contained
- Effects **may** accept an optional arena: `update(delta_time, arena=None)`.
- The MS2 `Arena` uses signature inspection to detect if the effect accepts an arena parameter, and if so, passes itself (the arena instance) when calling `update()`. The arena is never stored in the effect, only passed as a parameter.
- If you need to track a character, store `owner_id` and look it up when `arena` is provided.

### Example: Correct Pattern
```python
class MyEffect(TimedEffect):
    def __init__(self, cow, mouse_pos):
        super().__init__(list(cow.location), 1.0)
        self.owner_id = cow.id  # ✅ Store ID, not object
        self.cow_size = cow.size  # ✅ Store size if needed for drawing
        self.mouse_pos = mouse_pos  # ✅ Primitive data
        
        # ❌ DON'T: self.cow = cow
        # ❌ DON'T: store arena or other complex objects
    
    def update(self, delta_time: float, arena=None) -> bool:
        if arena is not None:
            cow = next((c for c in arena.characters if c.id == self.owner_id), None)
            if cow is None:
                return True  # Owner missing: expire effect
            self.location[0] = cow.location[0]
            self.location[1] = cow.location[1]
        return super().update(delta_time)
    
    def draw(self, screen, arena_height, camera=None):
        # Use stored cow_size, not self.cow.size
        radius = self.cow_size / 2
        # ... draw ...
```

### Why This Matters
When effects are serialized via `__getstate__()` and sent over the network, complex objects cannot be properly reconstructed on the client. The client will receive strings or broken references instead of objects, causing `AttributeError` crashes like `'str' object has no attribute 'size'`.

**Reference**: See `WaveProjectileEffect`, `RadialEffect`, `ConeEffect`, `LineEffect` for examples of correct patterns.
