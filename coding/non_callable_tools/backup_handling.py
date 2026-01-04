import os
import shutil
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

    def create_backup(self, path: str, recursive: bool = True, auto_naming: bool = True):
        """
        Create a backup of a file or directory.

        Args:
            path: Path to the file or directory to backup
            recursive: If True, backup directories recursively (default: True)

        Returns:
            Path to the created backup
        """
        if not os.path.exists(path):
            raise ValueError(f"Path {path} does not exist")

        if auto_naming:
            backup_name = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + os.path.basename(path)
        else:
            backup_name = os.path.basename(path)
        backup_path = os.path.join(self.backup_folder, backup_name)
        
        if os.path.isfile(path):
            # Backup file
            shutil.copy2(path, backup_path)
            return backup_path
        elif os.path.isdir(path):
            # Backup directory
            if os.path.exists(backup_path):
                # rename the already existing backup
                new_backup_name = backup_name + "_" + datetime.now().strftime("%Y%m%d%H%M%S")
                new_backup_path = os.path.join(self.backup_folder, new_backup_name)
                shutil.move(backup_path, new_backup_path)
                if os.path.exists(backup_path):
                    print("ERROR: Failed to rename backup")
                    input("Press Enter to continue...")
                else:
                    print("Renamed backup to ", new_backup_name)
                    input("Press Enter to continue...")
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
        
        return True

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