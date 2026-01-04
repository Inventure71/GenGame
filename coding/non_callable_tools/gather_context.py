from coding.tools.file_handling import get_tree_directory, read_file
import os

def get_full_directory_tree():
    """Returns combined directory tree with access labels."""
    context = (
        f"## Accessible Directories\n"
        f"### GameFolder/ [READ + WRITE]\n"
        f"{get_tree_directory('GameFolder')}\n"
        f"### BASE_components/ [READ-ONLY - do NOT modify]\n"
        f"{get_tree_directory('BASE_components')}\n"
    )
    return context

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
    context = (
        f"=== STARTING CONTEXT ===\n"
        f"{get_full_directory_tree()}\n"
        f"**Access Rules:**\n"
        f"- GameFolder/: You can read and write files here\n"
        f"- BASE_components/: Read-only, inherit from these classes in GameFolder/\n\n"
        f"Do NOT call get_tree_directory - use the paths above.\n\n"
        f"=== END OF STARTING CONTEXT ==="
    )
    return context

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

def gather_context_fix(results: dict) -> str:
    """Gather focused context for fix mode - only error files + directory tree."""
    lines = [
        "=== FIX MODE CONTEXT ===",
        "",
        get_full_directory_tree(),  # Directory structure
        "",
        "## Files Involved in Errors:",
        gather_context_fixing_errors(results),  # Only error-related files
        "",
        "=== END OF FIX CONTEXT ==="
    ]
    return "\n".join(lines)

# helpers
import re
from typing import Set

def gather_context_fixing_errors(results: dict):
    """Gather context from all files involved in test failures."""
    if results is None:
        print("Handle gracefully the case where results is None")
        return ""
    files_to_read = get_all_files_involved_in_errors(results)
    
    context_lines = [
        "=== FILES INVOLVED IN ERRORS ===",
        f"Found {len(files_to_read)} files mentioned in errors:",
    ]
    
    for file_path in sorted(files_to_read):
        context_lines.append(f"\n### {file_path}")
        if os.path.exists(file_path):
            try:
                content = read_file(file_path)
                context_lines.append(content)
            except Exception as e:
                context_lines.append(f"Error reading file: {e}")
        else:
            context_lines.append("File not found")
    
    context_lines.append("\n=== END OF ERROR FILES ===")
    return "\n".join(context_lines)

def extract_files_from_error(error_msg: str, traceback: str) -> Set[str]:
    """
    Extract all Python file paths mentioned in error messages and tracebacks.
    
    Args:
        error_msg: The error message string
        traceback: The full traceback string
        
    Returns:
        Set of file paths mentioned in the error
    """
    files = set()
    
    # Pattern for Python traceback file lines: File "/path/to/file.py", line 123, in function
    file_pattern = r'File "([^"]*\.py)"'
    
    # Extract from error message
    if error_msg:
        matches = re.findall(file_pattern, error_msg)
        files.update(matches)
    
    # Extract from traceback
    if traceback:
        matches = re.findall(file_pattern, traceback)
        files.update(matches)
    
    return files

def get_all_files_involved_in_errors(results: dict) -> Set[str]:
    """
    Extract all unique file paths involved in test failures.
    
    Args:
        results: Test results dictionary from run_all_tests()
        
    Returns:
        Set of all file paths mentioned in any error
    """
    all_files = set()
    
    if not results.get("success", True):
        for failure in results.get("failures", []):
            # Always include the test source file
            if failure.get("source_file"):
                all_files.add(failure["source_file"])
            
            # Extract additional files from error and traceback
            error_files = extract_files_from_error(
                failure.get("error_msg", ""),
                failure.get("traceback", "")
            )
            all_files.update(error_files)
    
    return all_files