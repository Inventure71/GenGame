"""
Patch Manager - Handles patch metadata and selection for multiplayer games.
Uses the database for storage; patch files are only used for transmission (e.g. to server).
"""
import os
import json
import tempfile
from typing import List, Dict, Optional, Tuple

from BASE_files.patch_database import DEFAULT_DB_FILENAME, PatchDatabase


class PatchInfo:
    """Information about a patch (from file or database)."""
    def __init__(self, name: str, base_backup: str, num_changes: int, file_path: Optional[str] = None, patch_id: Optional[int] = None):
        self.file_path = file_path
        self.patch_id = patch_id
        self.name = name
        self.base_backup = base_backup
        self.num_changes = num_changes
        self.selected = False
    
    def __repr__(self):
        return f"PatchInfo({self.name}, base={self.base_backup}, changes={self.num_changes})"


class PatchManager:
    """Manages patch discovery, metadata extraction, and selection. Uses database for storage."""

    def __init__(self, patches_directory: str = "__patches", db_path: Optional[str] = None):
        self.patches_directory = os.path.abspath(patches_directory)
        self.available_patches: List[PatchInfo] = []
        self.selected_patches: List[PatchInfo] = []
        self.max_selections = 1
        self._patch_db = None
        # Default: database lives inside patches directory (same default as PatchDatabase)
        resolved_db_path = db_path if db_path else os.path.join(self.patches_directory, DEFAULT_DB_FILENAME)
        try:
            db_dir = os.path.dirname(resolved_db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            self._patch_db = PatchDatabase(resolved_db_path)  # creates file and tables if missing
        except Exception as e:
            print(f"PatchManager: could not open database {resolved_db_path}: {e}")
        
    def scan_patches(self) -> List[PatchInfo]:
        """
        Load patches from the database (or from directory if DB not configured).
        Returns list of PatchInfo objects.
        """
        self.available_patches = []
        if self._patch_db:
            self._scan_patches_from_db()
        else:
            self._scan_patches_from_directory()
        print(f"Found {len(self.available_patches)} patches")
        return self.available_patches
    
    def _scan_patches_from_db(self) -> None:
        """Load patch list from the database."""
        try:
            items, total = self._patch_db.get_patches_page(0, 10000, search="")
            for item in items:
                num_changes = item.get('num_changes')
                if num_changes is None:
                    num_changes = 0
                try:
                    num_changes = int(num_changes)
                except (TypeError, ValueError):
                    num_changes = 0
                name = item.get('name') or f"Patch {item.get('patch_id', '?')}"
                self.available_patches.append(PatchInfo(
                    name=name,
                    base_backup=item.get('base_backup', 'Unknown'),
                    num_changes=num_changes,
                    file_path=None,
                    patch_id=int(item['patch_id']) if item.get('patch_id') else None
                ))
        except Exception as e:
            print(f"Failed to load patches from database: {e}")
    
    def _scan_patches_from_directory(self) -> None:
        """Load patch list from the patches directory."""
        if not os.path.exists(self.patches_directory):
            print(f"Patches directory not found: {self.patches_directory}")
            return
        patch_files = [f for f in os.listdir(self.patches_directory)
                      if f.endswith('.json') and not f.startswith('merge_') and not f.endswith('_metadata.json')]
        for patch_file in patch_files:
            full_path = os.path.join(self.patches_directory, patch_file)
            patch_info = self._extract_patch_metadata(full_path)
            if patch_info:
                self.available_patches.append(patch_info)
    
    def _extract_patch_metadata(self, file_path: str) -> Optional[PatchInfo]:
        """
        Extract metadata from a patch JSON file.
        Returns PatchInfo or None if invalid.
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            name = os.path.basename(file_path).replace('.json', '')
            base_backup = data.get('name_of_backup', 'Unknown')
            changes = data.get('changes', [])
            num_changes = len(changes)
            return PatchInfo(name=name, base_backup=base_backup, num_changes=num_changes, file_path=file_path, patch_id=None)
        except Exception as e:
            print(f"Failed to read patch {file_path}: {e}")
            return None
    
    def toggle_selection(self, patch_index: int) -> bool:
        """
        Toggle selection of a patch. Returns True if selection changed.
        Enforces max_selections limit.
        """
        if patch_index < 0 or patch_index >= len(self.available_patches):
            return False
        
        patch = self.available_patches[patch_index]
        
        if patch.selected:
            # Deselect
            patch.selected = False
            if patch in self.selected_patches:
                self.selected_patches.remove(patch)
            return True
        else:
            # Select (if under limit)
            if len(self.selected_patches) < self.max_selections:
                patch.selected = True
                self.selected_patches.append(patch)
                return True
            else:
                print(f"Cannot select more than {self.max_selections} patches")
                return False
    
    def clear_selections(self):
        """Clear all patch selections."""
        for patch in self.available_patches:
            patch.selected = False
        self.selected_patches.clear()
    
    def get_selected_patch_paths(self) -> List[str]:
        """Get file paths of all selected patches (only for file-backed patches)."""
        return [patch.file_path for patch in self.selected_patches if patch.file_path]
    
    def get_selected_patches_info(self, current_username: str = None) -> List[Dict]:
        """Get info about selected patches for network transmission."""
        if current_username is None:
            print("ERROR: NO USERNAME PROVIDED")
            return [
                {'name': patch.name, 'base_backup': patch.base_backup, 'file_path': patch.file_path or '', 'num_changes': patch.num_changes}
                for patch in self.selected_patches
            ]
        
        updated_patches = []
        temp_files = []
        
        for patch in self.selected_patches:
            try:
                if patch.patch_id and self._patch_db:
                    # Load from database and write to temp file for sending
                    data = self._patch_db.get_patch_by_id(patch.patch_id)
                    if not data:
                        print(f"Error: patch {patch.name} (id={patch.patch_id}) not found in database")
                        continue
                    modified_patch_data = {
                        'name_of_backup': data.get('name_of_backup', 'Unknown'),
                        'prompt_used': data.get('prompt_used', ''),
                        'changes': list(data.get('changes', [])),
                    }
                    if data.get('game_hash'):
                        modified_patch_data['game_hash'] = data['game_hash']
                else:
                    # Load from file
                    if not patch.file_path or not os.path.exists(patch.file_path):
                        print(f"Error: patch file not found for {patch.name}")
                        continue
                    with open(patch.file_path, 'r') as f:
                        modified_patch_data = json.load(f)
                    modified_patch_data = json.loads(json.dumps(modified_patch_data))
                
                # Replace $USERNAME$ placeholder in all diff content
                if "changes" in modified_patch_data:
                    for change in modified_patch_data["changes"]:
                        if "diff" in change and "$USERNAME$" in change["diff"]:
                            change["diff"] = change["diff"].replace("$USERNAME$", current_username)
                            print(f"    ✓ Replaced $USERNAME$ with '{current_username}' in {change.get('path', 'unknown')}")
                
                temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
                json.dump(modified_patch_data, temp_file, indent=2)
                temp_file.close()
                temp_files.append(temp_file.name)
                
                updated_patches.append({
                    'name': patch.name,
                    'base_backup': patch.base_backup,
                    'file_path': temp_file.name,
                    'num_changes': patch.num_changes,
                    '_temp_file': True
                })
            except Exception as e:
                print(f"Error preparing patch {patch.name} for sending: {e}")
                print(f"Skipping patch {patch.name} due to preparation error to prevent server instability.")
        
        if hasattr(self, '_temp_patch_files'):
            self._temp_patch_files.extend(temp_files)
        else:
            self._temp_patch_files = temp_files

        return updated_patches

    def cleanup_temp_patch_files(self) -> None:
        """
        Delete temporary .json files created for sending patches to the server.
        Call this after the client has applied the merged patch from the server,
        so the single-patch files sent earlier are no longer needed.
        """
        if not getattr(self, '_temp_patch_files', None):
            return
        for path in self._temp_patch_files:
            try:
                if path and os.path.isfile(path):
                    os.remove(path)
            except OSError:
                pass
        self._temp_patch_files.clear()
        
    def validate_patch_compatibility(self, patches_info_list: List[List[Dict]]) -> Tuple[bool, Optional[str]]:
        """
        Validate that all patches from all clients use the same base backup.
        
        Args:
            patches_info_list: List of patch info lists from each client
        
        Returns:
            (is_compatible, error_message)
        """
        all_base_backups = set()
        
        for client_patches in patches_info_list:
            for patch_info in client_patches:
                all_base_backups.add(patch_info.get('base_backup', 'Unknown'))
        
        if len(all_base_backups) == 0:
            return True, None  # No patches selected
        
        if len(all_base_backups) > 1:
            return False, f"Incompatible base backups: {', '.join(all_base_backups)}"
        
        return True, None

    def delete_patch(self, patch_index: int) -> bool:
        """
        Delete a patch by index (from database or from file).
        Returns True if successful, False otherwise.
        """
        if patch_index < 0 or patch_index >= len(self.available_patches):
            return False

        patch = self.available_patches[patch_index]

        try:
            if patch.selected and patch in self.selected_patches:
                self.selected_patches.remove(patch)

            if patch.patch_id and self._patch_db:
                self._patch_db.delete_patch(patch.patch_id)
                print(f"Deleted patch from database: {patch.name} (id={patch.patch_id})")
                self.available_patches.pop(patch_index)
                return True

            # File-backed patch
            if patch.file_path and os.path.exists(patch.file_path):
                os.remove(patch.file_path)
                print(f"Deleted patch file: {patch.file_path}")
            if patch.file_path:
                metadata_path = patch.file_path.replace(".json", "_metadata.json")
                if os.path.exists(metadata_path):
                    os.remove(metadata_path)
            self.available_patches.pop(patch_index)
            self.scan_patches()
            return True
        except Exception as e:
            print(f"Failed to delete patch {patch.name}: {e}")
            return False