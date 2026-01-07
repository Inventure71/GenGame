# GenGame Core Axioms

## Scope & Constraints
- **Access**: Only `GameFolder/` (read/write) and `BASE_components/` (read-only).
- **Documentation**: Use `BASE_components/BASE_COMPONENTS_DOCS.md` as the primary reference for all `BASE_` classes. Do NOT read files inside `BASE_components/` unless the documentation is insufficient.
- **Inheritance**: Always inherit from the appropriate BASE class in `GameFolder/` implementations.
- **New Entities**: Each weapon/projectile/etc. lives in its own file in the appropriate `GameFolder/` subdirectory.

## Technical Standards
- **Arena Dimensions**: Use `arena.width` and `arena.height`; never hardcode sizes.
- **Coordinates**: World = Y-up (logic). Screen = Y-down (rendering/rects). Always specify which.
- **Overrides**: Call `super().method_name()` unless fully replacing behavior.
- **Imports**: Use absolute imports: `from GameFolder...` or `from BASE_components...`

## Tool Efficiency - THINK FIRST, THEN BATCH CALLS

### CRITICAL: Always Use Parallel Tool Calls
**Before making ANY tool calls:**
1. **STOP and THINK**: What information do I need to accomplish this task?
2. **LIST ALL FILES/TOOLS** you'll need in your head
3. **MAKE ALL CALLS IN ONE TURN** - don't wait for results between independent calls

**Example - GOOD ✓:**
```
I need to understand TornadoGun, TornadoProjectile, and how weapons register.
[Calls read_file for all 3 files in parallel in ONE turn]
```

**Example - BAD ✗:**
```
I'll read TornadoGun.py first...
[waits for result]
Now I'll read TornadoProjectile.py...
[waits for result]
Now I'll read setup.py...
```

### Batching Rules
- **Target**: 5-10 parallel tool calls per turn when gathering information
- **Don't Limit Yourself**: If you need 8 files, read all 8 at once
- **Independence Check**: If tool call B doesn't need results from tool call A, make them parallel
- **Applies to ALL tools**: Reading, writing, searching, analyzing - batch everything that's independent

### Other Efficiency Rules
- **Large Files**: Use `get_file_outline` to map line numbers, then read only what you need.
- **Don't Re-read**: After `modify_file_inline`, use the returned context; only `read_file` if you need other sections.
- **Don't Repeat**: Context provided at the start of each task includes the directory tree. Only refresh with `get_tree_directory` after creating new files.

## Common Pitfalls
- **Ghost Bugs**: Put physics/behavior in entities, not Arena manager.
- **Coordinate Confusion**: Specify Y-up or Y-down for every position calculation.
- **Path Guessing**: Use only paths from the provided directory tree or discovered via tools.

## ⚖️ Physics & Speed Standards (60 FPS)
### Projectile Speed Limits
To prevent "tunneling" (skipping over targets), follow these speed tiers:
- **Standard**: 15.0 - 25.0 (Reliable and visible)
- **Fast**: 26.0 - 40.0 (Still reliable against standard 50px characters)
- **⚠️ Danger Zone**: 45.0+ (Will likely skip collisions and appear to vanish)

### Character Scale & Collision
- **Default Size**: 50x50 pixels.
- **Scaling**: If a character is scaled down (e.g., `scale_ratio = 0.5`), the projectile speed safety limit drops proportionally (e.g., max safe speed = 25.0).

### Jump & Gravity Context
- **Gravity**: 0.4 pixels/frame².
- **Jump Height**: ~280 pixels total height.
- **Flight/Airtime**: Standard jump lasts ~1.25 seconds.