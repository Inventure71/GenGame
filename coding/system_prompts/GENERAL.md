# GenGame Core Axioms

## Scope & Constraints
- **Access**: Only `GameFolder/` (read/write) and `BASE_components/` (read-only).
- **BASE_components**: Inherit from these classes in `GameFolder/`; never modify them.
- **New Entities**: Each weapon/projectile/etc. lives in its own file in the appropriate `GameFolder/` subdirectory.

## Technical Standards
- **Arena Dimensions**: Use `arena.width` and `arena.height`; never hardcode sizes.
- **Coordinates**: World = Y-up (logic). Screen = Y-down (rendering/rects). Always specify which.
- **Overrides**: Call `super().method_name()` unless fully replacing behavior.
- **Imports**: Use absolute imports: `from GameFolder...` or `from BASE_components...`

## Tool Efficiency
- **Batch Calls**: Call 3-6 tools per turn in parallel when possible.
- **Read Limits**: Max 6 read tools per turn; max 6 write tools per turn.
- **Don't Re-read**: After `modify_file_inline`, use the returned context; only `read_file` if you need other sections.
- **Don't Repeat**: Context provided at the start of each task includes the directory tree. Only refresh with `get_tree_directory` after creating new files.

## Common Pitfalls
- **Ghost Bugs**: Put physics/behavior in entities, not Arena manager.
- **Coordinate Confusion**: Specify Y-up or Y-down for every position calculation.
- **Path Guessing**: Use only paths from the provided directory tree or discovered via tools.
