"""
Standalone conflict resolution tools for 3-way merge patches.
These functions work with JSON patch files containing unified diffs with conflict markers.
"""
import json
from typing import Dict, List, Optional


# =============================================================================
# PATCH FILE I/O
# =============================================================================

def load_patch_file(patch_path: str) -> tuple:
    """
    Load a patch JSON file.
    Returns: (name_of_backup, changes_list)
    """
    with open(patch_path, 'r') as f:
        data = json.load(f)
    return data.get("name_of_backup", ""), data.get("changes", [])


def save_patch_file(patch_path: str, name_of_backup: str, changes: List[Dict]) -> None:
    """Save changes back to a patch JSON file."""
    with open(patch_path, 'w') as f:
        json.dump({"name_of_backup": name_of_backup, "changes": changes}, f, indent=2)


# =============================================================================
# CONFLICT PARSING HELPERS
# =============================================================================

def _strip_diff_prefix(line: str) -> str:
    """Remove diff prefix (+/-/space) if present."""
    if line and line[0] in ('+', '-', ' '):
        return line[1:]
    return line


def _is_conflict_start(line: str) -> bool:
    return _strip_diff_prefix(line).startswith('<<<<<<< ')


def _is_conflict_separator(line: str) -> bool:
    return _strip_diff_prefix(line).startswith('=======')


def _is_conflict_end(line: str) -> bool:
    return _strip_diff_prefix(line).startswith('>>>>>>> ')


def _parse_conflicts_from_diff(diff: str) -> List[Dict]:
    """
    Parse all conflicts from a diff string.
    Returns list of dicts with: conflict_num, option_a, option_b, start_line_idx, end_line_idx
    """
    lines = diff.splitlines()
    conflicts = []
    i = 0
    conflict_num = 0
    
    while i < len(lines):
        if _is_conflict_start(lines[i]):
            conflict_num += 1
            start_idx = i
            option_a = []
            option_b = []
            
            i += 1
            while i < len(lines) and not _is_conflict_separator(lines[i]):
                option_a.append(_strip_diff_prefix(lines[i]))
                i += 1
            i += 1  # Skip =======
            while i < len(lines) and not _is_conflict_end(lines[i]):
                option_b.append(_strip_diff_prefix(lines[i]))
                i += 1
            end_idx = i
            
            conflicts.append({
                'conflict_num': conflict_num,
                'option_a': option_a,
                'option_b': option_b,
                'start_line_idx': start_idx,
                'end_line_idx': end_idx
            })
        i += 1
    
    return conflicts


# =============================================================================
# PUBLIC API - TOOL FUNCTIONS
# =============================================================================

def get_all_conflicts(patch_path: str) -> Dict[str, List[Dict]]:
    """
    Get all conflicts from a patch file, organized by file path.
    
    Args:
        patch_path: Path to the merged patch JSON file
    
    Returns:
        Dict mapping file_path -> list of conflict dicts
        Each conflict has: conflict_num, option_a, option_b, start_line_idx, end_line_idx
    """
    name, changes = load_patch_file(patch_path)
    
    result = {}
    for change in changes:
        diff = change.get('diff', '')
        if '<<<<<<< ' not in diff:
            continue
        
        conflicts = _parse_conflicts_from_diff(diff)
        if conflicts:
            result[change['path']] = conflicts
    
    return result


# Global tracker for resolutions applied during LLM process
_resolution_tracker = {}

def get_resolution_tracker():
    """Get the global resolution tracker."""
    global _resolution_tracker
    return _resolution_tracker

def clear_resolution_tracker():
    """Clear the resolution tracker."""
    global _resolution_tracker
    _resolution_tracker = {}

def resolve_conflict(patch_path: str = None, file_path: str = None,
                     conflict_num: int = None, resolution: str = None,
                     manual_content: list = None, **kwargs) -> str:
    """
    Resolves a specific merge conflict in a patch file.
    
    Args:
        patch_path: Path to the merged patch JSON file
        file_path: The file containing the conflict (e.g., 'GameFolder/arenas/GAME_arena.py')
        conflict_num: Which conflict to resolve (1-indexed)
        resolution: 'a' (use patch A), 'b' (use patch B), 'both' (keep both), 'manual' (custom)
        manual_content: Lines of code when resolution is 'manual' (list of strings)
    
    Returns:
        Success or error message
    """
    # Validate required params
    missing = []
    if not patch_path: missing.append("patch_path")
    if not file_path: missing.append("file_path")
    if conflict_num is None: missing.append("conflict_num")
    if not resolution: missing.append("resolution")
    
    if missing:
        return f"Error: Missing required arguments: {missing}"
    
    if resolution not in ('a', 'b', 'both', 'manual'):
        return f"Error: Invalid resolution '{resolution}'. Must be 'a', 'b', 'both', or 'manual'"
    
    if resolution == 'manual' and not manual_content:
        return "Error: manual_content required when resolution is 'manual'"
    
    try:
        name, changes = load_patch_file(patch_path)
    except FileNotFoundError:
        return f"Error: Patch file not found: {patch_path}"
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON in patch file: {e}"
    
    # Find the file with the conflict
    for change in changes:
        if change['path'] != file_path:
            continue
        
        diff = change.get('diff', '')
        conflicts = _parse_conflicts_from_diff(diff)
        
        # Find the target conflict
        target = None
        for c in conflicts:
            if c['conflict_num'] == conflict_num:
                target = c
                break
        
        if not target:
            return f"Error: Conflict #{conflict_num} not found in '{file_path}'"
        
        # Build replacement lines
        if resolution == 'a':
            replacement = ['+' + l for l in target['option_a']]
        elif resolution == 'b':
            replacement = ['+' + l for l in target['option_b']]
        elif resolution == 'both':
            replacement = ['+' + l for l in target['option_a']]
            replacement.extend(['+' + l for l in target['option_b']])
        elif resolution == 'manual':
            replacement = ['+' + l for l in (manual_content or [])]
        
        # Replace the conflict block in the diff
        lines = diff.splitlines()
        new_lines = lines[:target['start_line_idx']] + replacement + lines[target['end_line_idx'] + 1:]
        change['diff'] = '\n'.join(new_lines)
        
        # Track the resolution for caching
        global _resolution_tracker
        key = f"{file_path}:{conflict_num}"
        if resolution == 'manual':
            _resolution_tracker[key] = {"manual_content": manual_content}
        else:
            _resolution_tracker[key] = {"resolution": resolution}

        # Save the updated patch
        save_patch_file(patch_path, name, changes)
        return f"Successfully resolved conflict #{conflict_num} in '{file_path}' using '{resolution}'"
    
    return f"Error: File '{file_path}' not found in patch"


def resolve_conflicts_interactive(patch_path: str) -> bool:
    """
    Interactively resolve all conflicts via command line prompts.
    Returns True if all conflicts were resolved.
    
    Note: This is for CLI use, not for LLM tool calls.
    """
    name, changes = load_patch_file(patch_path)
    
    # Get all conflicts
    conflicts_by_file = {}
    for change in changes:
        diff = change.get('diff', '')
        if '<<<<<<< ' not in diff:
            continue
        conflicts = _parse_conflicts_from_diff(diff)
        if conflicts:
            conflicts_by_file[change['path']] = conflicts
    
    if not conflicts_by_file:
        print("No conflicts found!")
        return True
    
    for file_path, conflicts in conflicts_by_file.items():
        print(f"\n{'='*60}")
        print(f"CONFLICT in: {file_path}")
        print('='*60)
        
        for conflict in conflicts:
            print(f"\n--- Conflict #{conflict['conflict_num']} ---")
            print("[A] Option:")
            for l in conflict['option_a']:
                print(f"  {l}")
            print("\n[B] Option:")
            for l in conflict['option_b']:
                print(f"  {l}")
            
            while True:
                ans = input("\nChoose [A], [B], [BOTH], or [M]anual: ").strip().lower()
                if ans in ('a', 'b', 'both'):
                    result = resolve_conflict(patch_path, file_path, conflict['conflict_num'], ans)
                    print(result)
                    break
                elif ans == 'm':
                    print("Enter your resolution (type END on a new line to finish):")
                    manual_lines = []
                    while True:
                        line = input()
                        if line == 'END':
                            break
                        manual_lines.append(line)
                    result = resolve_conflict(patch_path, file_path, conflict['conflict_num'], 'manual', manual_lines)
                    print(result)
                    break
    
    # Check if any conflicts remain
    name, changes = load_patch_file(patch_path)
    for change in changes:
        if '<<<<<<< ' in change.get('diff', ''):
            return False
    return True

