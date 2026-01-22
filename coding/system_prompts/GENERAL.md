# Core Conflict Core Axioms

## Scope & Constraints
- **Access**: Only `GameFolder/` (read/write) and `BASE_components/` (read-only).
- **Documentation**: Use `BASE_components/BASE_COMPONENTS_DOCS.md` as the primary reference for all `BASE_` classes. Do NOT read files inside `BASE_components/` unless the documentation is insufficient.
- **Inheritance**: Always inherit from the appropriate BASE class in `GameFolder/` implementations.
- **New Entities**: Each ability/effect/pickup/arena feature lives in its own file in the appropriate `GameFolder/` subdirectory.
- **Game Perspective**: Top-down (overhead) 2D only. Not side-scrolling; effects/collisions stay on the X/Y plane (no Z-axis or platforming).

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
- **Hitbox Origin Confusion**: For characters and effects, `location` is a **world-space center point**, not a top-left. When creating `pygame.Rect` or collision boxes, you MUST center them: compute the rect origin as `[center_x - width/2, screen_y_from_center - height/2]` after doing the Y-up → Y-down conversion. Never treat `location` as the rect's top-left unless the class explicitly documents that. Always verify AoE effects can hit targets on both left and right sides (add tests for both directions).
- **Default Value Ambiguity**: Don't use valid runtime values (like `0.0` for timestamps) to mean "never happened". Use sentinels (`None`, `-1`) or handle the "never happened" case explicitly in conditionals.
- **Path Guessing**: Use only paths from the provided directory tree or discovered via tools.

## ⚖️ Gameplay Standards (60 FPS)
### Character Scale & Collision
- **No Starting Abilities**: Players always start with NO active (primary) abilities and NO passive abilities. All abilities must be acquired manually via weapon pickups in the arena. Never initialize characters with abilities in `setup.py` or anywhere else.
- **Default Size**: 30x30 pixels.
- **Scaling**: Larger cows are slower and smaller cows are faster; keep collision tests centered on world coordinates.

### Camera & World Size
- The server simulates the full world (`WORLD_WIDTH/WORLD_HEIGHT`); the client uses a camera to render a viewport.
- Convert input from screen → world on the client and always simulate in world space on the server.
