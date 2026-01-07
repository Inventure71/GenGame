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

## 🚨 CRITICAL RULE: PARALLEL TOOL USAGE IS MANDATORY 🚨

### NON-NEGOTIABLE: All Independent Tool Calls Must Be Batched

**Sequential tool calling is considered a CRITICAL ERROR. You MUST batch all independent tool calls.**

### The Rule (Zero Tolerance)
1. **THINK FIRST**: List ALL information you need
2. **BATCH EVERYTHING**: Make ALL independent tool calls in ONE response
3. **NEVER WAIT**: Don't make a call, wait for results, then make another call

**If you need N independent pieces of information, you MUST make N tool calls in ONE turn.**

### Examples

**✓ CORRECT - Parallel Batch:**
```
[THINKING: I need TornadoGun.py, TornadoProjectile.py, setup.py, and tornado_tests.py]
[IMMEDIATELY: read_file(TornadoGun.py) + read_file(TornadoProjectile.py) + read_file(setup.py) + read_file(tornado_tests.py) ALL IN ONE RESPONSE]
```

**✗ FORBIDDEN - Sequential Calls:**
```
Let me read TornadoGun.py first...
[waits for result - THIS IS WRONG]
Now let me read TornadoProjectile.py...
[waits for result - THIS IS WRONG]
```

### Enforcement
- **Minimum batch size**: If you need multiple files, read ALL of them at once
- **Typical batch size**: 5-15+ parallel calls when gathering context
- **No artificial limits**: Need 20 files? Read all 20 in one turn
- **Independence test**: If result of call B doesn't depend on call A, they MUST be parallel
- **Applies to ALL tools**: read_file, find_function_usages, get_function_source, list_functions, etc.

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