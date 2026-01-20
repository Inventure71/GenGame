# Core Conflict Core Axioms

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

## Player-Specific Logic in Multiplayer
- **Username Placeholder**: When modifying `GameFolder/setup.py` to apply logic to a specific player, use the exact placeholder `$USERNAME$` to reference the username of the player who requested the patch.
- **Patch Creator Context**: `$USERNAME$` represents the patch creator's username. Design implementations with this player as the primary target by default.
- **Unknown Players**: Other players' usernames are not available during patch creation. Use `$USERNAME$` only for the requesting player's logic.
- **Placeholder Replacement**: The system automatically replaces `$USERNAME$` with the actual player's username when patches are applied in multiplayer sessions.
- **Player Identification**: Use `player_name == "$USERNAME$"` or `"$USERNAME$" in player_name` for conditional logic targeting the patch creator's player.
- **No Hardcoding**: Never use player indices (e.g., `i == 0`) or hardcoded names for player-specific logic, as connection order varies in multiplayer.

## 🚨 PARALLEL TOOL USAGE IS MANDATORY 🚨

**Rule**: Think → list ALL files needed → batch ALL calls in ONE turn.

**Need N files? Make N calls in ONE response.**
- ✓ Correct: 4 files needed → 4 `read_file` calls at once
- ✗ Forbidden: Read one → wait → read another

**Efficiency**:
- Typical batch: 3-10+ calls (no artificial limits)
- Context includes directory tree; refresh only after creating new files

## Common Pitfalls
- **Ghost Bugs**: Put physics/behavior in entities, not Arena manager.
- **Coordinate Confusion**: Specify Y-up or Y-down for every position calculation.
- **Hitbox Origin Confusion**: For characters and projectiles, `location` is a **world-space center point**, not a top-left. When creating `pygame.Rect` or collision boxes, you MUST center them: compute the rect origin as `[center_x - width/2, screen_y_from_center - height/2]` after doing the Y-up → Y-down conversion. Never treat `location` as the rect's top-left unless the class explicitly documents that. Always verify melee/area-effect weapons can hit targets on both left and right sides (add tests for both directions).
- **Path Guessing**: Use only paths from the provided directory tree or discovered via tools.

## ⚖️ Physics & Speed Standards (60 FPS)
### Projectile Speed Limits
To prevent "tunneling" (skipping over targets), follow these speed tiers:
- **Standard**: 15.0 - 25.0 (Reliable and visible)
- **Fast**: 26.0 - 40.0 (Still reliable against standard 50px characters)
- **[warning] Danger Zone**: 45.0+ (Will likely skip collisions and appear to vanish)

### Character Scale & Collision
- **Default Size**: 30x30 pixels.
- **Scaling**: If a character is scaled down (e.g., `scale_ratio = 0.5`), the projectile speed safety limit drops proportionally (e.g., max safe speed = 25.0).

### Jump & Gravity Context
- **Gravity**: 0.4 pixels/frame².
- **Jump Height**: ~280 pixels total height.
- **Flight/Airtime**: Standard jump lasts ~1.25 seconds.