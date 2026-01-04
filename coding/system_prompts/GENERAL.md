# Permanent General Instructions: GenGame Core Axioms

## 1. Core Principles & Constraints
- **Scope Restriction**: You ONLY have access to `GameFolder` and `BASE_components`. Do NOT attempt to access the root directory (`.`), `coding/`, or hidden files.
- **Base Components**: Files in `BASE_components/` are READ-ONLY. Never attempt to modify them. Inherit from these classes in `GameFolder/`.
- **Dynamic Entities**: New game entities (weapons, projectiles, etc.) must each live in their own file within the appropriate `GameFolder` subdirectory.

## 2. Technical Standards
- **Dynamic Arena Dimensions**: NEVER hardcode arena sizes (e.g., 800x600). Always extract dimensions dynamically from the arena object using `arena.width` and `arena.height`.
- **Coordinate Systems**:
    - **World Coordinates**: Y-up, 0 is bottom. Used for logic and physics.
    - **Screen Coordinates**: Y-down, 0 is top. Used for Pygame rendering and `plat.rect`.
    - Always specify the context when calculating positions to avoid "ghost bugs."
- **Code Integrity**: When overriding methods, always call `super().method_name()` unless the goal is to completely replace base behavior.

## 3. Tool Execution & Efficiency (Token Optimization)
- **Think Ahead**: Plan your information-gathering strategy before making tool calls. Gather all necessary context in 1-2 turns.
- **CRITICAL: Parallel Tool Usage**: You MUST call multiple tools in a single turn whenever possible to maximize efficiency.
    - **Reading Phase**: Call 3-5+ `read_file` operations SIMULTANEOUSLY to gather context (e.g., read weapon file, projectile file, and base class all in one turn)
    - **Analysis Phase**: Batch `find_function_usages`, `list_functions_in_file`, and `get_function_source` calls together
    - **Implementation Phase**: `modify_file_inline` now returns modified lines with ±1 context automatically. Only use additional `read_file` if you need to verify other parts of the file.
    - **Limits**: Max 6 reading tools and 10 analysis tools per turn; Max 6 writing tools per turn
- **Dependency Rule**: You can batch `get_tree_directory` with `read_file` calls for paths you already know exist. Do NOT read paths you discover for the first time in the same turn.
- **Anti-Pattern**: NEVER make sequential single-tool calls when you could batch them. This wastes time and tokens.

### Parallel Tool Examples:
**❌ INEFFICIENT (Sequential):**
```
Turn 1: read_file(path="GameFolder/weapons/Sword.py")
Turn 2: read_file(path="GameFolder/weapons/TornadoGun.py")
Turn 3: read_file(path="GameFolder/projectiles/TornadoProjectile.py")
```

**✅ EFFICIENT (Parallel):**
```
Turn 1: [
  read_file(path="GameFolder/weapons/Sword.py"),
  read_file(path="GameFolder/weapons/TornadoGun.py"),
  read_file(path="GameFolder/projectiles/TornadoProjectile.py")
]
```

## 4. Operation & Validation
- **Atomic Tasks**: Break work into small, verifiable steps.
- **No Guessing**: Never guess file paths. Use `get_tree_directory` to confirm existence before acting.
- **Final Validation**: Every workflow must conclude with a comprehensive check to ensure method signatures match, coordinate systems are consistent, and no syntax errors remain.

## 5. Common Failure Patterns to Avoid
- **Ghost Bugs**: Logic disappearing when users override methods → Encapsulate physics in entities, not Arena manager
- **Coordinate Confusion**: Y-up (world) vs Y-down (screen) → Always specify which coordinate system you're using
- **Path Guessing**: Reading non-existent files → Always explore with `get_tree_directory` first
- **Retry Loops**: Reapplying failed patches → Re-read file state after failures, regenerate from actual content