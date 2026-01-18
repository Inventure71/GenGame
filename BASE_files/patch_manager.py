"""
Patch Manager - Handles patch metadata and selection for multiplayer games
"""
import os
import json
from typing import List, Dict, Optional, Tuple


class PatchInfo:
    """Information about a patch file."""
    def __init__(self, file_path: str, name: str, base_backup: str, num_changes: int):
        self.file_path = file_path
        self.name = name
        self.base_backup = base_backup
        self.num_changes = num_changes
        self.selected = False
    
    def __repr__(self):
        return f"PatchInfo({self.name}, base={self.base_backup}, changes={self.num_changes})"


class PatchManager:
    """Manages patch discovery, metadata extraction, and selection."""
    
    def __init__(self, patches_directory: str = "__patches"):
        self.patches_directory = patches_directory
        self.available_patches: List[PatchInfo] = []
        self.selected_patches: List[PatchInfo] = []
        self.max_selections = 3
        
    def scan_patches(self) -> List[PatchInfo]:
        """
        Scan the patches directory and extract metadata from all patch files.
        Returns list of PatchInfo objects.
        """
        self.available_patches = []
        
        if not os.path.exists(self.patches_directory):
            print(f"Patches directory not found: {self.patches_directory}")
            return []
        
        # Find all .json files in the patches directory
        patch_files = [f for f in os.listdir(self.patches_directory) 
                      if f.endswith('.json') and not f.startswith('merge_') and not f.endswith('_metadata.json')]
        
        for patch_file in patch_files:
            full_path = os.path.join(self.patches_directory, patch_file)
            patch_info = self._extract_patch_metadata(full_path)
            if patch_info:
                self.available_patches.append(patch_info)
        
        print(f"Found {len(self.available_patches)} patches")
        return self.available_patches
    
    def _extract_patch_metadata(self, file_path: str) -> Optional[PatchInfo]:
        """
        Extract metadata from a patch JSON file.
        Returns PatchInfo or None if invalid.
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Extract patch name (from filename without extension)
            name = os.path.basename(file_path).replace('.json', '')
            
            # Extract base backup name
            base_backup = data.get('name_of_backup', 'Unknown')
            
            # Count changes
            changes = data.get('changes', [])
            num_changes = len(changes)
            
            return PatchInfo(file_path, name, base_backup, num_changes)
        
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
        """Get file paths of all selected patches."""
        return [patch.file_path for patch in self.selected_patches]
    
    def get_selected_patches_info(self, current_username: str = None) -> List[Dict]:
        """Get info about selected patches for network transmission."""
        if current_username is None:   
            print("ERROR: NO USERNAME PROVIDED")
            return [
                {
                    'name': patch.name,
                    'base_backup': patch.base_backup,
                    'file_path': patch.file_path,
                    'num_changes': patch.num_changes
                }
                for patch in self.selected_patches
            ]
        
        import tempfile
        updated_patches = []
        temp_files = []  # Track temp files for cleanup
        
        for patch in self.selected_patches:
            try:
                # Read the original patch file (we don't modify it)
                with open(patch.file_path, 'r') as f:
                    patch_data = json.load(f)
                
                # Create a copy for modification
                modified_patch_data = json.loads(json.dumps(patch_data))  # Deep copy
                
                # Replace $USERNAME$ placeholder in all diff content in the copy
                if "changes" in modified_patch_data:
                    for change in modified_patch_data["changes"]:
                        if "diff" in change and "$USERNAME$" in change["diff"]:
                            change["diff"] = change["diff"].replace("$USERNAME$", current_username)
                            print(f"    ✓ Replaced $USERNAME$ with '{current_username}' in {change.get('path', 'unknown')}")
                
                # Create a temporary file with the modified patch
                temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
                json.dump(modified_patch_data, temp_file, indent=2)
                temp_file.close()
                temp_files.append(temp_file.name)
                
                # Return info pointing to the temp file
                updated_patches.append({
                    'name': patch.name,
                    'base_backup': patch.base_backup,
                    'file_path': temp_file.name,  # Point to temp file, not original
                    'num_changes': patch.num_changes,
                    '_temp_file': True  # Flag to clean up later
                })
            except Exception as e:
                print(f"Error preparing patch {patch.name} for sending: {e}")
                # Still include original file path if modification fails
                updated_patches.append({
                    'name': patch.name,
                    'base_backup': patch.base_backup,
                    'file_path': patch.file_path,
                    'num_changes': patch.num_changes
                })
        
        # Store temp files for cleanup (you might want to clean them up after sending)
        # For now, we'll rely on the OS to clean them up, or you can add cleanup logic
        if hasattr(self, '_temp_patch_files'):
            self._temp_patch_files.extend(temp_files)
        else:
            self._temp_patch_files = temp_files
        
        return updated_patches
        
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

