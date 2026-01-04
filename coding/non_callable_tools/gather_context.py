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
