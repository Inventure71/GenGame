import os
import re
import json
import ast
import glob
from typing import Tuple, List
from coding.non_callable_tools.backup_handling import BackupHandler
from coding.tools.modify_inline import modify_file_inline
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