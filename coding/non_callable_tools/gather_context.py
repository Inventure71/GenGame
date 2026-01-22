from coding.tools.file_handling import get_tree_directory, read_file
from coding.non_callable_tools.helpers import open_file
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

def gather_context_enchancer():
    """Gathers context for the enchancer phase."""
    lines = [
        "## Context given:",
        "Documentation of BASE game components:",
        read_file(file_path='BASE_components/BASE_COMPONENTS_DOCS.md'),
    ]
    return "\n".join(lines)

def gather_context_planning():
    """Gathers comprehensive context for the planning phase."""
    lines = [
        "=== STARTING CONTEXT (Already gathered - do NOT re-read these files) ===",
        "",
        get_full_directory_tree(),
        "",
        "## Documentation of BASE components:",
        read_file(file_path="BASE_components/BASE_COMPONENTS_DOCS.md"),
        "## Guide for adding abilities:",
        open_file(file_path="coding/prompts/GUIDE_Adding_Abilities.md"),
    ]
    
    # Read core game files
    lines.append("\n## Core Game Files (extend BASE classes here):")
    for filepath in [
        'GameFolder/arenas/GAME_arena.py',
        'GameFolder/characters/GAME_character.py',
        'GameFolder/effects/coneeffect.py',
        'GameFolder/effects/radialeffect.py',
        'GameFolder/effects/lineeffect.py',
        'GameFolder/effects/waveprojectileeffect.py',
        'GameFolder/effects/obstacleeffect.py',
        'GameFolder/effects/zoneindicator.py',
        'GameFolder/pickups/GAME_pickups.py',
        'GameFolder/world/GAME_world_objects.py',
        'GameFolder/abilities/ability_loader.py',
    ]:
        lines.append(f"\n### {filepath}")
        lines.append(read_file(file_path=filepath))
    
    # Setup configuration
    lines.append("\n## Setup Configuration:")
    lines.append(read_file(file_path='GameFolder/setup.py'))
    
    lines.append("\n=== END OF STARTING CONTEXT ===")
    lines.append("\n⚡ REMINDER: Make ALL read_file calls in PARALLEL in ONE turn. Never read sequentially. ⚡")
    
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
        f"=== END OF STARTING CONTEXT ===\n\n"
        f"⚡ REMINDER: Use tools in PARALLEL. If you need multiple files, read ALL of them in ONE response. ⚡"
    )
    return context

def gather_context_testing():
    """Gathers context for the testing phase, including critical pitfalls."""
    lines = [
        "=== TESTING CONTEXT ===",
        "",
        get_full_directory_tree(),
        "",
        "⚡ CRITICAL REMINDER: Batch ALL file reads in ONE turn (5-10+ parallel calls is expected). Sequential reading is FORBIDDEN. ⚡",
        "",
        "## 🚨 EXECUTION ORDER WARNING (CRITICAL FOR COLLISION TESTS):",
        "When testing collisions, effects, or pickups:",
        "1. `handle_collisions()` calls `_resolve_obstacle_collisions()` FIRST",
        "2. This MOVES characters if they overlap obstacles",
        "3. Effect/pickup checks happen AFTER obstacle resolution",
        "4. If you place entities at character's initial location, they won't collide!",
        "5. SOLUTION: Call `handle_collisions()` first, capture final location, then place entities",
        "6. See GUIDE_Testing.md section 6.5 for detailed patterns and examples",
        "",
        "## CRITICAL: Character & Ability Attributes",
        "Before writing tests, note these BASE_components facts:",
        "",
        "### Character (BASE_character.py)",
        "- Health attribute: `character.health` (NOT `hp`)",
        "- `character.is_alive` is a read-only property: `health > 0 AND lives > 0`",
        "- To kill: `character.health = 0`",
        "- Dimensions use: `char.width * char.scale_ratio`",
        "",
        "### Primary Ability Usage",
        "- `character.use_primary_ability(arena, mouse_pos)` consumes a charge when allowed",
        "- Cooldown is enforced by `character.primary_use_cooldown` and `last_primary_use`",
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
        open_file(file_path="coding/prompts/GUIDE_Testing.md"),
        "",
        "=== END OF TESTING CONTEXT ==="
    ]
    return "\n".join(lines)

def gather_context_fix(results: dict) -> str:
    """Gather focused context for fix mode - only error files + directory tree."""
    lines = [
        "=== FIX CONTEXT ===",
        "",
        get_full_directory_tree(),  # Directory structure
        "",
        "⚡ CRITICAL REMINDER: Batch ALL tool calls in ONE turn (read_file, get_file_outline, get_function_source, etc.). 5-20+ parallel calls is expected. Sequential calls are FORBIDDEN. ⚡",
        "",
        "## Execution Order Warning:",
        "If test fails with 'no collision' or 'entity not found' despite correct setup:",
        "1. Read the method called in the test (e.g., handle_collisions)",
        "2. Trace ALL methods it calls in order",
        "3. Check if ANY method modifies state (location, health, etc.) BEFORE the assertion",
        "4. If yes, the test setup may need to account for these mutations",
        "5. Common pattern: collision resolution methods move entities before effect/pickup checks",
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

def extract_files_and_lines_from_error(error_msg: str, traceback: str) -> dict:
    """
    Extract file paths and their associated line numbers from error messages and tracebacks.
    
    Args:
        error_msg: The error message string
        traceback: The full traceback string
        
    Returns:
        Dict mapping file paths to sets of line numbers mentioned in the error
    """
    files_and_lines = {}
    
    # Pattern for Python traceback file lines: File "/path/to/file.py", line 123, in function
    file_line_pattern = r'File "([^"]*\.py)", line (\d+)'
    
    # Extract from error message
    if error_msg:
        matches = re.findall(file_line_pattern, error_msg)
        for file_path, line_num in matches:
            if file_path not in files_and_lines:
                files_and_lines[file_path] = set()
            files_and_lines[file_path].add(int(line_num))
    
    # Extract from traceback
    if traceback:
        matches = re.findall(file_line_pattern, traceback)
        for file_path, line_num in matches:
            if file_path not in files_and_lines:
                files_and_lines[file_path] = set()
            files_and_lines[file_path].add(int(line_num))
    
    return files_and_lines

def read_error_lines_from_file(file_path: str, line_numbers: Set[int], context_lines: int = 3) -> str:
    """
    Read specific lines from a file around the error locations.
    
    Args:
        file_path: Path to the file
        line_numbers: Set of line numbers involved in errors
        context_lines: Number of context lines to include around each error line
        
    Returns:
        String containing the relevant lines with context
    """
    if not os.path.exists(file_path):
        return f"File not found: {file_path}"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        # Sort line numbers and remove duplicates
        sorted_lines = sorted(line_numbers)
        
        # Collect all relevant line ranges
        ranges_to_show = []
        for line_num in sorted_lines:
            # Convert to 0-based indexing
            line_idx = line_num - 1
            if 0 <= line_idx < len(all_lines):
                start_line = max(0, line_idx - context_lines)
                end_line = min(len(all_lines), line_idx + context_lines + 1)
                ranges_to_show.append((start_line, end_line))
        
        # Merge overlapping ranges
        if ranges_to_show:
            merged_ranges = [ranges_to_show[0]]
            for start, end in ranges_to_show[1:]:
                last_start, last_end = merged_ranges[-1]
                if start <= last_end:
                    merged_ranges[-1] = (last_start, min(end, len(all_lines)))
                else:
                    merged_ranges.append((start, end))
            
            # Build the output
            output_lines = []
            for i, (start, end) in enumerate(merged_ranges):
                if i > 0:
                    output_lines.append("... (lines omitted) ...\n")
                
                for line_idx in range(start, end):
                    line_num = line_idx + 1
                    marker = ">>> " if line_num in line_numbers else "    "
                    line_content = all_lines[line_idx].rstrip('\n')
                    output_lines.append(f"{marker}{line_num:4d}|{line_content}\n")
            
            return "".join(output_lines)
        else:
            return f"No valid line numbers found in {file_path}"
            
    except Exception as e:
        return f"Error reading file {file_path}: {e}"

def gather_context_fixing_errors(results: dict):
    """Gather context from lines involved in test failures."""
    if results is None:
        print("Handle gracefully the case where results is None")
        return ""
    
    # Get files and their error line numbers
    files_and_lines = get_all_files_and_lines_involved_in_errors(results)
    
    context_lines = [
        "=== LINES INVOLVED IN ERRORS ===",
        f"Found {len(files_and_lines)} files with errors:",
    ]
    
    for file_path in sorted(files_and_lines.keys()):
        context_lines.append(f"\n### {file_path}")
        line_numbers = files_and_lines[file_path]
        error_lines_content = read_error_lines_from_file(file_path, line_numbers)
        context_lines.append(error_lines_content)
    
    context_lines.append("\n=== END OF ERROR LINES ===")
    return "\n".join(context_lines)

def get_all_files_and_lines_involved_in_errors(results: dict) -> dict:
    """
    Extract all unique file paths and their line numbers involved in test failures.
    
    Args:
        results: Test results dictionary from run_all_tests()
        
    Returns:
        Dict mapping file paths to sets of line numbers mentioned in errors
    """
    all_files_and_lines = {}
    
    if not results.get("success", True):
        for failure in results.get("failures", []):
            # Only include the test source file if it's an absolute path that exists
            if failure.get("source_file"):
                file_path = failure["source_file"]
                # Skip relative paths that don't exist (traceback will have full paths anyway)
                if os.path.isabs(file_path) and os.path.exists(file_path):
                    if file_path not in all_files_and_lines:
                        all_files_and_lines[file_path] = set()
            
            # Extract additional files and line numbers from error and traceback
            error_files_and_lines = extract_files_and_lines_from_error(
                failure.get("error_msg", ""),
                failure.get("traceback", "")
            )
            
            # Merge the dictionaries
            for file_path, line_nums in error_files_and_lines.items():
                if file_path not in all_files_and_lines:
                    all_files_and_lines[file_path] = set()
                all_files_and_lines[file_path].update(line_nums)
    
    return all_files_and_lines
