from coding.tools.file_handling import get_tree_directory, read_file
import os


def get_full_directory_tree():
    """Returns combined directory tree with access labels."""
    return f"""## Accessible Directories

### GameFolder/ [READ + WRITE]
{get_tree_directory("GameFolder")}

### BASE_components/ [READ-ONLY - do NOT modify]
{get_tree_directory("BASE_components")}"""


def gather_context_planning():
    """Gathers comprehensive context for the planning phase."""
    lines = [
        "=== STARTING CONTEXT (Already gathered - do NOT re-read these files) ===",
        "",
        get_full_directory_tree(),
        "",
        "## BASE Components Contents (read-only, inherit from these):",
    ]
    
    # Read all BASE_components files
    base_components_path = "BASE_components"
    for filename in sorted(os.listdir(base_components_path)):
        if filename.endswith('.py') and not filename.startswith('__'):
            filepath = os.path.join(base_components_path, filename)
            lines.append(f"\n### {filename}")
            lines.append(read_file(filepath))
    
    # Read core game files
    lines.append("\n## Core Game Files (extend BASE classes here):")
    for filepath in [
        'GameFolder/arenas/GAME_arena.py',
        'GameFolder/characters/GAME_character.py',
        'GameFolder/projectiles/GAME_projectile.py',
        'GameFolder/weapons/GAME_weapon.py',
    ]:
        lines.append(f"\n### {filepath}")
        lines.append(read_file(filepath))
    
    # Setup configuration
    lines.append("\n## Setup Configuration:")
    lines.append(read_file('GameFolder/setup.py'))
    
    lines.append("\n=== END OF STARTING CONTEXT ===")
    
    return "\n".join(lines)


def gather_context_coding():
    """Gathers minimal context for the coding phase (tree only, files read on demand)."""
    return f"""=== STARTING CONTEXT ===

{get_full_directory_tree()}

**Access Rules:**
- GameFolder/: You can read and write files here
- BASE_components/: Read-only, inherit from these classes in GameFolder/

Do NOT call get_tree_directory - use the paths above.

=== END OF STARTING CONTEXT ==="""


def gather_context_testing():
    """Gathers context for the testing phase, including critical pitfalls."""
    lines = [
        "=== TESTING CONTEXT ===",
        "",
        get_full_directory_tree(),
        "",
        "## CRITICAL: Character & Weapon Attributes",
        "Before writing tests, note these BASE_components facts:",
        "",
        "### Character (BASE_character.py)",
        "- Health attribute: `character.health` (NOT `hp`)",
        "- `character.is_alive` is a read-only property: `health > 0 AND lives > 0`",
        "- To kill: `character.health = 0`",
        "- Dimensions use: `char.width * char.scale_ratio`",
        "",
        "### Weapon Cooldowns",
        "- `weapon.shoot()` returns `None` if cooldown hasn't elapsed",
        "- Create NEW weapon instances per test, or reset: `weapon.last_shot_time = 0`",
        "",
        "### Timing in Tests",
        "- Use INTEGER frame counting, not float accumulation:",
        "  `for _ in range(int(duration / dt)): ...` NOT `while total < duration: total += dt`",
        "",
        "### Arena Effects",
        "- `arena.handle_collisions(dt)` applies ALL effects each call (damage, knockback, recoil)",
        "- Effects ACCUMULATE across loop iterations",
        "",
        "## Testing Guide:",
        read_file("coding/prompts/GUIDE_Testing.md"),
        "",
        "=== END OF TESTING CONTEXT ==="
    ]
    return "\n".join(lines)
