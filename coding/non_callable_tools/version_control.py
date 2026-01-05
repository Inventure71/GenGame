import os
import re
import json
import ast
import glob
import difflib
from typing import Tuple, List, Dict, Optional
from coding.non_callable_tools.backup_handling import BackupHandler
from coding.tools.modify_inline import modify_file_inline, _apply_unified_diff_safe
from coding.non_callable_tools.action_logger import ActionLogger

def extract_successful_tools(action_logger):
    all_tools_used = action_logger.actions

    # Each action contains:
    # {
    #     "type": "tool_call",
    #     "name": "create_file",  # Tool name
    #     "success": True,
    #     "timestamp": datetime_obj,
    #     "args": {...},          # Compact args
    #     "args_full": {...},     # Full args
    #     "result": "...",        # Compact result
    #     "result_full": "..."    # Full result
    # }

    successful_tools = [
        action["name"] for action in all_tools_used 
        if action["success"]
    ]

    return successful_tools

class VersionControl:
    def __init__(self, action_logger_instance: ActionLogger = None, path_to_security_backup: str = "__TEMP_SECURITY_BACKUP"):
        self.action_logger_instance = action_logger_instance
        self.security_backup_handler = BackupHandler(path_to_security_backup)
    
    def save_to_extension_file(self, file_path: str, name_of_backup: str = None):
        if self.action_logger_instance is None:
            print("ERROR: Action logger instance is not provided")
            return False
        changes = []
        metadata = []
        for path in self.action_logger_instance.file_changes:
            original = self.action_logger_instance.file_snapshots.get(path, "")
            final = self.action_logger_instance.file_changes.get(path, "")
            if original != final:
                changes.append({
                    "path": path,
                    "diff": self.action_logger_instance.get_diff(path)
                    })
                metadata.append({
                    "path": path,
                    "original": original,
                    "final": final
                })
        if len(changes) > 0:
            if name_of_backup is None or name_of_backup == "":
                name_of_backup = "GameFolder"
            with open(file_path, 'w') as f:
                json.dump({"name_of_backup": name_of_backup, "changes": changes}, f)
            with open(file_path.replace('.json', '_metadata.json'), 'w') as f:
                json.dump({"name_of_backup": name_of_backup, "metadata": metadata}, f)
            return True
        else:
            print("No changes to save")
            return False

    def load_from_extension_file(self, file_path: str):
        with open(file_path, 'r') as f:
            data = json.load(f)
            name_of_backup = data["name_of_backup"]
            changes = data["changes"]
        if os.path.exists(file_path.replace('.json', '_metadata.json')):
            with open(file_path.replace('.json', '_metadata.json'), 'r') as f:
                metadata = json.load(f)
        else:
            print(f"No metadata file found for {file_path}")
            metadata = []
        return name_of_backup, changes, metadata
    
    def valid_apply(self, file_path: str, diff: str) -> bool:
        result = modify_file_inline(file_path=file_path, diff_text=diff)
        if result.startswith("Successfully modified"):
            return True, result
        else:
            return False, result

    def apply_patches(self, file_containing_patches: str):
        success_count = 0
        any_fixed = False
        name_of_backup, changes, metadata = self.load_from_extension_file(file_containing_patches)
        for change in changes:
            file_path = change["path"]
            print(f"Applying patch to {file_path}...")
            # check if it exists
            if not os.path.exists(file_path):
                print(f"File {file_path} does not exist, creating")
                with open(file_path, 'w') as f:
                    f.write('')
            
            diff = change["diff"]
            if diff:
                success, result = self.valid_apply(file_path, diff)
                if success:
                    print(f"    ✓ Applied successfully")
                    success_count += 1
                else:
                    print(f"    ✗ Failed Default Patching: {result}, repairing...")
                    repaired_diff = self.repair_smashed_patch(file_path, result, change["diff"])
                    if repaired_diff != change["diff"]:
                        print(f"    ✅ Repair successful. Updating patches.json and retrying...")
                        change["diff"] = repaired_diff
                        any_fixed = True
                        # Retry immediately with the fixed diff
                        success, result = self.valid_apply(file_path, repaired_diff)
                        if success:
                            print(f"    ✓ Applied successfully")
                            success_count += 1
                        else:
                            print(f"    ✗ Failed Repaired Patching: {result}")
                    else:
                        print(f"    ✗ Failed Acquiring Repaired Patch: {result}")

        if any_fixed:
            print(f"Saving fixed patches to {file_containing_patches}...")
            with open(file_containing_patches, 'w') as f:
                json.dump({"name_of_backup": name_of_backup, "changes": changes}, f)

        return success_count == len(changes), success_count, len(changes)

    def merge_all_changes(self, needs_rebase: bool = False, path_to_BASE_backup: str = None, file_containing_patches: str = None):
        if file_containing_patches is None:
            print("ERROR: File containing patches is not provided")
            return False

        name_of_backup, changes, metadata = self.load_from_extension_file(file_containing_patches)

        if needs_rebase:
            if path_to_BASE_backup is not None:
                print("Rebasing changes")
                print("Name of backup to find: ", name_of_backup)
                if name_of_backup is None or name_of_backup == "":
                    print("ERROR: No name of backup provided in the patches file, cannot rebase")
                    return False

                base_backup_handler = BackupHandler(path_to_BASE_backup)
                available_backups = base_backup_handler.list_backups()
                if name_of_backup not in available_backups:
                    print("ERROR: No base backup found, cannot rebase")
                    print("Available backups: ", available_backups)
                    print("Name of backup to find: ", name_of_backup)
                    return False
                base_backup_handler.restore_backup(name_of_backup, target_path="GameFolder")
                print("Restored to base code")
                input("Press Enter to continue...")
            else:
                print("ERROR:No base backup provided but needs rebase, cannot rebase")
                return False

        print("Creating temporary backup")
        self.security_backup_handler.create_backup("GameFolder", auto_naming=False)

        print("Applying all changes")
        success, count, total_changes =self.apply_patches(file_containing_patches)

        print(f"Applied {count}/{total_changes} changes successfully")

        if not success:
            print("Failed to apply all changes, restoring to temporary backup")
            self.security_backup_handler.restore_backup("GameFolder", target_path="GameFolder")
            print("Restored, removing temporary backup")
            self.security_backup_handler.delete_entire_backup_folder()
            return False
        
        print("All changes applied successfully")
        print("Removing temporary backup")
        self.security_backup_handler.delete_entire_backup_folder()
        
        print("All changes applied successfully")
        return True

    # =========================================================================
    # 3-WAY MERGE
    def merge_patches(self, base_backup_path: str, patch_a_path: str, patch_b_path: str, output_path: str = None) -> Tuple[bool, str]:
        """
        Merges two patches that were both created from the same base backup.
        
        Args:
            base_backup_path: Path to the backup folder containing base files
            patch_a_path: Path to the first patch JSON file
            patch_b_path: Path to the second patch JSON file
            output_path: Optional output path for merged patch (default: merged_patch.json)
        
        Returns:
            Tuple of (success: bool, output_path_or_error: str)
        """
        if output_path is None:
            output_path = "merged_patch.json"
        
        # Load both patches
        name_a, changes_a, _ = self.load_from_extension_file(patch_a_path)
        name_b, changes_b, _ = self.load_from_extension_file(patch_b_path)
        
        # Verify both patches are from the same base
        if name_a != name_b:
            return False, f"ERROR: Patches have different bases ({name_a} vs {name_b}). Cannot merge."
        
        # Verify base backup exists
        if not os.path.exists(base_backup_path):
            return False, f"ERROR: Base backup path does not exist: {base_backup_path}"
        
        # Build maps: path -> diff
        map_a = {c['path']: c['diff'] for c in changes_a}
        map_b = {c['path']: c['diff'] for c in changes_b}
        all_paths = set(map_a.keys()) | set(map_b.keys())
        
        merged_changes = []
        conflicts_found = []
        
        for rel_path in sorted(all_paths):
            diff_a = map_a.get(rel_path)
            diff_b = map_b.get(rel_path)
            
            # Case 1: Only one patch touches this file
            if diff_a and not diff_b:
                merged_changes.append({"path": rel_path, "diff": diff_a})
                print(f"  {rel_path}: Using patch A (only)")
                continue
            if diff_b and not diff_a:
                merged_changes.append({"path": rel_path, "diff": diff_b})
                print(f"  {rel_path}: Using patch B (only)")
                continue
            
            # Case 2: Both patches touch this file - need 3-way merge
            print(f"  {rel_path}: Both patches modify - performing 3-way merge...")
            
            # Get base content
            base_content = self._get_base_content(base_backup_path, rel_path, name_a)
            if base_content is None:
                base_content = ""  # New file in both patches
            
            # Apply each patch to base to get the two versions
            version_a = self._apply_diff_to_content(base_content, diff_a)
            version_b = self._apply_diff_to_content(base_content, diff_b)
            
            if version_a is None or version_b is None:
                conflicts_found.append(rel_path)
                print(f"    ERROR: Could not apply patches to compute versions")
                continue
            
            # Perform 3-way merge
            merged_content, has_conflicts = self._three_way_merge(base_content, version_a, version_b)
            
            # Validate merged content didn't lose critical lines
            validation_issues = self._validate_merge_content(base_content, version_a, version_b, merged_content)
            if validation_issues:
                print(f"    WARNING: Merge validation issues detected:")
                for issue in validation_issues:
                    print(f"      - {issue}")
            
            if has_conflicts:
                conflicts_found.append(rel_path)
                print(f"    CONFLICT: Manual resolution required")
                # Still include it with conflict markers
            else:
                print(f"    OK: Auto-merged successfully")
            
            # Generate unified diff from base to merged
            merged_diff = self._generate_unified_diff(base_content, merged_content, rel_path)
            if merged_diff:
                merged_changes.append({"path": rel_path, "diff": merged_diff})
        
        # Write output
        with open(output_path, 'w') as f:
            json.dump({"name_of_backup": name_a, "changes": merged_changes}, f, indent=2)
        
        if conflicts_found:
            return False, f"Merged with {len(conflicts_found)} conflicts in: {conflicts_found}. Output: {output_path}"
        
        return True, output_path
    
    def _get_base_content(self, base_backup_path: str, rel_path: str, backup_name: str) -> Optional[str]:
        """Gets content of a file from the base backup."""
        # rel_path is like "GameFolder/arenas/GAME_arena.py"
        # base_backup_path might be "__game_backups" and backup_name "20260104161653_GameFolder"
        
        # Try direct path first (if base_backup_path contains the full backup)
        if rel_path.startswith("GameFolder/"):
            # The backup structure mirrors the original, so we strip "GameFolder/"
            inner_path = rel_path[len("GameFolder/"):]
            full_path = os.path.join(base_backup_path, backup_name, inner_path)
        else:
            full_path = os.path.join(base_backup_path, backup_name, rel_path)
        
        if os.path.exists(full_path):
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        # Try without backup_name (if base_backup_path IS the backup folder)
        if rel_path.startswith("GameFolder/"):
            inner_path = rel_path[len("GameFolder/"):]
            full_path = os.path.join(base_backup_path, inner_path)
        else:
            full_path = os.path.join(base_backup_path, rel_path)
            
        if os.path.exists(full_path):
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        return None
    
    def _apply_diff_to_content(self, base_content: str, diff_text: str) -> Optional[str]:
        """Applies a unified diff to content and returns the result.
        Reuses the robust _apply_unified_diff_safe from modify_inline.py."""
        try:
            result, _ = _apply_unified_diff_safe(base_content, diff_text)
            return result
        except ValueError as e:
            print(f"    Warning: Could not apply diff cleanly: {e}")
            return None
    
    def _three_way_merge(self, base: str, version_a: str, version_b: str) -> Tuple[str, bool]:
        """
        Performs a 3-way merge between base, version_a, and version_b.
        Returns (merged_content, has_conflicts).
        """
        # Handle empty base (new file case)
        if not base.strip():
            if version_a == version_b:
                return version_a, False
            elif not version_a.strip():
                return version_b, False
            elif not version_b.strip():
                return version_a, False
            else:
                # Both patches create different content for a new file
                has_conflicts = True
                merged = "<<<<<<< PATCH_A\n" + version_a + "\n=======\n" + version_b + "\n>>>>>>> PATCH_B\n"
                return merged.rstrip('\n'), has_conflicts
        
        base_lines = base.splitlines(keepends=True)
        a_lines = version_a.splitlines(keepends=True)
        b_lines = version_b.splitlines(keepends=True)
        
        # Ensure all lines end with newline for consistent comparison
        if base_lines and not base_lines[-1].endswith('\n'):
            base_lines[-1] += '\n'
        if a_lines and not a_lines[-1].endswith('\n'):
            a_lines[-1] += '\n'
        if b_lines and not b_lines[-1].endswith('\n'):
            b_lines[-1] += '\n'
        
        # Use difflib to find changes from base to each version
        matcher_a = difflib.SequenceMatcher(None, base_lines, a_lines)
        matcher_b = difflib.SequenceMatcher(None, base_lines, b_lines)
        
        # Build change lists with intervals: (start_base, end_base, removed_lines, new_lines)
        changes_a = self._extract_changes_list(matcher_a, a_lines, base_lines)
        changes_b = self._extract_changes_list(matcher_b, b_lines, base_lines)
        
        # Track which changes have been processed
        used_a = set()
        used_b = set()
        
        merged = []
        has_conflicts = False
        i = 0  # Current position in base
        
        while i < len(base_lines):
            # Find changes that start at or cover position i
            change_a, idx_a = self._find_change_at(changes_a, i, used_a)
            change_b, idx_b = self._find_change_at(changes_b, i, used_b)
            
            # Also check if there's an overlapping change from the other side
            if change_a is not None and change_b is None:
                change_b, idx_b = self._find_overlapping_change(changes_b, change_a, used_b)
            elif change_b is not None and change_a is None:
                change_a, idx_a = self._find_overlapping_change(changes_a, change_b, used_a)
            
            if change_a is None and change_b is None:
                # No changes at this position
                merged.append(base_lines[i])
                i += 1
            elif change_a is not None and change_b is None:
                # Only A changed this region
                merged.extend(change_a['new_lines'])
                used_a.add(idx_a)
                # For INSERT (start == end), no base lines consumed - don't skip any
                # For REPLACE/DELETE, skip past consumed base lines
                if change_a['end_base'] > change_a['start_base']:
                    i = change_a['end_base']
                # else: INSERT - i stays same, next iteration writes base_lines[i]
            elif change_b is not None and change_a is None:
                # Only B changed this region
                merged.extend(change_b['new_lines'])
                used_b.add(idx_b)
                # For INSERT (start == end), no base lines consumed - don't skip any
                # For REPLACE/DELETE, skip past consumed base lines
                if change_b['end_base'] > change_b['start_base']:
                    i = change_b['end_base']
                # else: INSERT - i stays same, next iteration writes base_lines[i]
            else:
                # Both changed - mark both as used
                used_a.add(idx_a)
                used_b.add(idx_b)
                
                if change_a['new_lines'] == change_b['new_lines']:
                    merged.extend(change_a['new_lines'])
                else:
                    # Both patches modified the same region with different results
                    has_conflicts = True
                    
                    # Check if both are INSERT operations (start_base == end_base, no lines removed)
                    is_insert_a = change_a['start_base'] == change_a['end_base']
                    is_insert_b = change_b['start_base'] == change_b['end_base']
                    
                    if is_insert_a and is_insert_b:
                        # Both patches INSERT at the same position
                        # Add conflict with both insertions
                        merged.append("<<<<<<< PATCH_A\n")
                        merged.extend(change_a['new_lines'])
                        merged.append("=======\n")
                        merged.extend(change_b['new_lines'])
                        merged.append(">>>>>>> PATCH_B\n")
                        # For INSERT, we still need to write base_lines[i]
                        # Don't advance i - the next iteration will write it
                        # But we've used up these changes
                        i = i  # Stay at current position to write base line next iteration
                        continue  # Skip the i = max(...) below
                    else:
                        # At least one is a REPLACE/DELETE - true conflict
                        merged.append("<<<<<<< PATCH_A\n")
                        merged.extend(change_a['new_lines'])
                        merged.append("=======\n")
                        merged.extend(change_b['new_lines'])
                        merged.append(">>>>>>> PATCH_B\n")
                
                # Advance past consumed base lines (use max of end_base values)
                # Don't add +1 since end_base already points past consumed lines
                max_end = max(change_a['end_base'], change_b['end_base'])
                if max_end > i:
                    i = max_end
                else:
                    # Both were INSERTs at same position, don't advance
                    # (this case should have been handled above with continue)
                    pass
        
        return ''.join(merged).rstrip('\n'), has_conflicts
    
    def _extract_changes_list(self, matcher: difflib.SequenceMatcher, new_lines: List[str], base_lines: List[str]) -> List[Dict]:
        """Extracts a list of changes with their intervals from a SequenceMatcher.
        Also stores removed lines to detect accidental removals during merge."""
        changes = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                continue
            # i1:i2 is the range in base, j1:j2 is range in new
            changes.append({
                'start_base': i1,
                'end_base': i2,
                'removed_lines': base_lines[i1:i2],  # Track what was removed
                'new_lines': new_lines[j1:j2],
                'tag': tag  # 'replace', 'delete', or 'insert'
            })
        return changes
    
    def _find_change_at(self, changes: List[Dict], pos: int, used: set) -> Tuple[Optional[Dict], Optional[int]]:
        """Find a change that covers or starts at position pos."""
        for idx, change in enumerate(changes):
            if idx in used:
                continue
            # Check if pos is within the change's base range
            if change['start_base'] <= pos < change['end_base']:
                return change, idx
            # Also check for insertions (start == end) at this position
            if change['start_base'] == change['end_base'] == pos:
                return change, idx
        return None, None
    
    def _find_overlapping_change(self, changes: List[Dict], other_change: Dict, used: set) -> Tuple[Optional[Dict], Optional[int]]:
        """Find a change that overlaps with other_change's base range."""
        other_start = other_change['start_base']
        other_end = other_change['end_base']
        
        for idx, change in enumerate(changes):
            if idx in used:
                continue
            # Check for any overlap between ranges
            if change['start_base'] < other_end and change['end_base'] > other_start:
                return change, idx
        return None, None
    
    def _validate_merge_content(self, base: str, version_a: str, version_b: str, merged: str) -> List[str]:
        """
        Validates that the merged content contains expected lines from both versions.
        Returns a list of potential issues found.
        """
        issues = []
        merged_lines = set(line.strip() for line in merged.splitlines() if line.strip())
        base_lines = set(line.strip() for line in base.splitlines() if line.strip())
        
        # Check for critical code patterns that should be preserved
        critical_patterns = [
            r'^\s*elif isinstance\(.*\):',  # elif isinstance checks
            r'^\s*if isinstance\(.*\):',    # if isinstance checks
            r'^\s*class \w+',               # class definitions
            r'^\s*def \w+',                 # function definitions
        ]
        
        for pattern in critical_patterns:
            # Find matches in version_a that aren't in base (new code from patch A)
            for line in version_a.splitlines():
                if re.match(pattern, line) and line.strip() not in base_lines:
                    if line.strip() not in merged_lines:
                        issues.append(f"Patch A code may be missing: {line.strip()[:60]}...")
            
            # Find matches in version_b that aren't in base (new code from patch B)
            for line in version_b.splitlines():
                if re.match(pattern, line) and line.strip() not in base_lines:
                    if line.strip() not in merged_lines:
                        issues.append(f"Patch B code may be missing: {line.strip()[:60]}...")
        
        # Check that base elif/if chains are preserved (unless intentionally modified)
        for line in base.splitlines():
            stripped = line.strip()
            if stripped.startswith('elif isinstance(') or stripped.startswith('if isinstance('):
                # This base line should either be in merged OR be modified in one of the patches
                if stripped not in merged_lines:
                    # Check if it was intentionally removed/modified by a patch
                    in_version_a = stripped in set(l.strip() for l in version_a.splitlines())
                    in_version_b = stripped in set(l.strip() for l in version_b.splitlines())
                    
                    if in_version_a and in_version_b:
                        # Both patches kept it but it's missing from merge - this is a bug!
                        issues.append(f"Base code lost during merge: {stripped[:60]}...")
        
        return issues
    
    def _generate_unified_diff(self, base_content: str, new_content: str, file_path: str) -> str:
        """Generates a unified diff between base and new content."""
        base_lines = base_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        # Ensure trailing newlines
        if base_lines and not base_lines[-1].endswith('\n'):
            base_lines[-1] += '\n'
        if new_lines and not new_lines[-1].endswith('\n'):
            new_lines[-1] += '\n'
        
        diff = difflib.unified_diff(
            base_lines, new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}"
        )
        return ''.join(diff)

    # =========================================================================
    # HELPERS
    def repair_smashed_patch(self, file_path: str, error_msg: str, original_diff: str) -> str:
        """
        Analyzes a failed patch error, detects smashed lines, and repairs the diff.
        """
        # 1. Extract the problematic line from the error message
        # Looking for: Diff wants to remove: '...'
        match = re.search(r"Diff wants to (?:remove|add): '(.+?)'", error_msg)
        if not match:
            return original_diff
        
        problem_line_content = match.group(1)
        
        # 2. Generalizable Smashed Line Detection
        # Look for an internal '+' or '-' preceded by code and followed by 4+ spaces/indentation
        # Example: "code()+        code()"
        smashed_pattern = r"(.+?)([\+\-])(\s{4,}.+)"
        smashed_match = re.search(smashed_pattern, problem_line_content)
        
        if not smashed_match:
            return original_diff

        left_part = smashed_match.group(1).strip()
        internal_marker = smashed_match.group(2)
        right_part = smashed_match.group(3).strip()

        # 3. Apply your "Compare & Fix" logic
        if left_part == right_part:
            # If identical, we only keep the first one
            fixed_content = left_part
        else:
            # If different, we split them into two separate lines
            # We must maintain the correct diff markers for both
            fixed_content = f"{left_part}\n{internal_marker} {right_part}"

        # 4. Replace the broken line in the original diff
        # We escape the problem line to use it safely in a regex replacement
        escaped_problem = re.escape(problem_line_content)
        # The [+-] at the start of the diff line is preserved
        repaired_diff = re.sub(f"([\\+\\-])\\s*{escaped_problem}", f"\\1 {fixed_content}", original_diff)
        
        return repaired_diff

    def validate_folder_integrity(self, folder_path: str) -> Tuple[bool, List[str]]:
        """
        Validates the integrity of the GameFolder before operations.
        Returns (is_valid, list_of_issues)
        """
        issues = []
        
        # 1. Check expected file structure
        expected_structure = {
            "arenas/GAME_arena.py": "exists",
            "characters/GAME_character.py": "exists", 
            "platforms/GAME_platform.py": "exists",
            "projectiles/GAME_projectile.py": "exists",
            "weapons/GAME_weapon.py": "exists",
            "ui/GAME_ui.py": "exists",
            "setup.py": "exists"
        }
        
        for path, requirement in expected_structure.items():
            full_path = os.path.join(folder_path, path)
            if not os.path.exists(full_path):
                issues.append(f"CRITICAL: Missing required file: {path}")
            elif requirement == "exists" and os.path.getsize(full_path) == 0:
                issues.append(f"WARNING: Empty required file: {path}")
        
        # 2. Syntax validation for all Python files
        py_files = glob.glob(os.path.join(folder_path, "**/*.py"), recursive=True)
        for py_file in py_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for syntax errors
                ast.parse(content)
                                
            except SyntaxError as e:
                issues.append(f"SYNTAX ERROR in {py_file}: Line {e.lineno}: {e.msg}")
            except UnicodeDecodeError:
                issues.append(f"ENCODING ERROR in {py_file}: Not valid UTF-8")
            except Exception as e:
                issues.append(f"ERROR reading {py_file}: {str(e)}")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    