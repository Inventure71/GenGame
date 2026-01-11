import os
import shutil
import hashlib
from datetime import datetime
"""
Backup and restore system for directories, subdirectories, and files.
- Create backups of entire directories, subdirectories, and files
- Restore backups to original locations, overwriting existing files
"""

class BackupHandler:
    def __init__(self, backup_folder: str = "backups"):
        self.backup_folder = backup_folder
        # Ensure backup folder exists
        os.makedirs(self.backup_folder, exist_ok=True)

    def compute_directory_hash(self, path: str) -> str:
        """
        Compute SHA256 hash of entire directory content.
        Includes all file paths and contents for 100% uniqueness.
        """
        hasher = hashlib.sha256()
        
        # Get all files in sorted order for consistent hashing
        file_paths = []
        for root, dirs, files in os.walk(path):
            # Sort directories and files for consistent ordering
            dirs.sort()
            for file in sorted(files):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, path)
                file_paths.append((rel_path, full_path))
        
        # Hash each file: relative_path + content
        for rel_path, full_path in file_paths:
            try:
                # Hash the relative path first
                hasher.update(rel_path.encode('utf-8'))
                hasher.update(b'\x00')  # Separator
                
                # Hash file content
                with open(full_path, 'rb') as f:
                    while chunk := f.read(8192):
                        hasher.update(chunk)
                
                hasher.update(b'\x01')  # File separator
            except (IOError, OSError):
                # Skip unreadable files
                continue

        return hasher.hexdigest()

    def create_backup(self, path: str, recursive: bool = True, auto_naming: bool = True):
        """
        Create a backup of a file or directory.
        
        For hash-based naming, if a backup with the same hash already exists,
        returns the existing backup instead of creating a duplicate.
        
        Args:
            path: Path to the file or directory to backup
            recursive: If True, backup directories recursively (default: True)
            auto_naming: If True, use hash-based naming (default: True)
        
        Returns:
            Tuple of (backup_path, backup_name)
        """
        if not os.path.exists(path):
            raise ValueError(f"Path {path} does not exist")

        # Generate backup name
        if auto_naming:
            backup_name = self.compute_directory_hash(path)
        else:
            backup_name = os.path.basename(path)
        
        backup_path = os.path.join(self.backup_folder, backup_name)

        # If backup with this name already exists, return it (no duplicates)
        if os.path.exists(backup_path):
            print(f"Backup already exists: {backup_name}")
            return backup_path, backup_name

        # Create new backup
        if os.path.isfile(path):
            # Backup single file
            shutil.copy2(path, backup_path)
            return backup_path, backup_name
            
        elif os.path.isdir(path):
            # Backup directory
            if recursive:
                shutil.copytree(path, backup_path)
            else:
                # Non-recursive: create directory and copy only immediate files
                os.makedirs(backup_path, exist_ok=True)
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    if os.path.isfile(item_path):
                        shutil.copy2(item_path, backup_path)
            return backup_path, backup_name
        else:
            raise ValueError(f"Path {path} is not a file or directory")

    def restore_backup(self, backup_name: str, target_path: str = None):
        """
        Restore a backup to the target location, overwriting existing files.

        Args:
            backup_name: Name of the backup to restore
            target_path: Where to restore to. If None, uses the original name
        """
        backup_path = os.path.join(self.backup_folder, backup_name)

        if not os.path.exists(backup_path):
            raise ValueError(f"Backup {backup_name} does not exist")

        # Determine target path
        if target_path is None:
            target_path = backup_name

        # Ensure target directory exists
        target_dir = os.path.dirname(target_path)
        if target_dir and not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        # Remove existing target if it exists
        if os.path.exists(target_path):
            if os.path.isfile(target_path):
                os.remove(target_path)
            elif os.path.isdir(target_path):
                shutil.rmtree(target_path)

        # Restore the backup
        if os.path.isfile(backup_path):
            shutil.copy2(backup_path, target_path)
        elif os.path.isdir(backup_path):
            shutil.copytree(backup_path, target_path)
        else:
            raise ValueError(f"Backup {backup_name} is corrupted")
        
        return backup_path, backup_name

    def list_backups(self):
        """
        List all available backups.

        Returns:
            List of backup names
        """
        if not os.path.exists(self.backup_folder):
            return []
        return [item for item in os.listdir(self.backup_folder)
                if os.path.exists(os.path.join(self.backup_folder, item))]

    def delete_backup(self, backup_name: str):
        """
        Delete a backup.

        Args:
            backup_name: Name of the backup to delete
        """
        backup_path = os.path.join(self.backup_folder, backup_name)
        if not os.path.exists(backup_path):
            raise ValueError(f"Backup {backup_name} does not exist")

        if os.path.isfile(backup_path):
            os.remove(backup_path)
        elif os.path.isdir(backup_path):
            shutil.rmtree(backup_path)
    
    def delete_entire_backup_folder(self):
        """
        Delete the entire backup folder.
        """
        if not os.path.exists(self.backup_folder):
            raise ValueError(f"Backup folder {self.backup_folder} does not exist")
        shutil.rmtree(self.backup_folder)