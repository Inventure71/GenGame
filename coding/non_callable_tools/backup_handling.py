import os
import shutil
import hashlib
from datetime import datetime
import unicodedata

from coding.non_callable_tools.helpers import should_skip_item, copytree_filtered
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
    
    def _normalize_rel_path(self, rel_path: str) -> str:
        """
        Normalize a relative path for cross-platform stability:
        - Use forward slashes
        - Collapse '.' and '..'
        - Normalize Unicode to NFC (important for macOS vs Linux)
        """
        p = rel_path.replace("\\", "/")

        # Collapse '.' and '..'
        parts = p.split("/")
        out: list[str] = []
        for part in parts:
            if part in ("", "."):
                continue
            if part == "..":
                if out:
                    out.pop()
                continue
            out.append(part)

        normalized = "/".join(out)

        # Unicode normalization (macOS filenames can differ)
        normalized = unicodedata.normalize("NFC", normalized)

        return normalized

    def compute_directory_hash(
        self,
        path: str,
        *,
        debug: bool = False,
        strict_read_errors: bool = True,
    ) -> str:
        """
        Compute a SHA256 hash over a directory's content + normalized relative paths.

        Cross-platform stability features:
        - relative paths (not absolute)
        - normalized separators to '/'
        - Unicode NFC normalization for filenames
        - deterministic walk order (sorted dirs/files)
        - explicit skip list for junk/caches

        Parameters
        ----------
        debug:
            If True, prints the normalized paths included in the hash (useful to diff dev vs Docker).
        strict_read_errors:
            If True, raises on unreadable files (recommended for reproducibility).
            If False, includes a deterministic '__UNREADABLE__' marker instead.
        """
        base_path = os.path.abspath(os.path.normpath(path))
        hasher = hashlib.sha256()

        file_entries: list[tuple[str, str]] = []

        for root, dirs, files in os.walk(base_path, topdown=True, followlinks=False):
            # Filter + sort dirs for deterministic traversal
            dirs[:] = [d for d in dirs if not should_skip_item(d)]
            dirs.sort()

            for name in sorted(files):
                if should_skip_item(name):
                    continue

                full_path = os.path.join(root, name)
                rel_path = os.path.relpath(full_path, base_path)

                # os.path.relpath can theoretically return '.' only when comparing identical paths;
                # for files it should never be '.', but keep it safe anyway.
                if rel_path == ".":
                    rel_path = name

                normalized_rel = self._normalize_rel_path(rel_path)
                file_entries.append((normalized_rel, full_path))

        # Sort by normalized rel path so hashing order is stable
        file_entries.sort(key=lambda x: x[0])

        if debug:
            print("BASE:", base_path)
            for p, _ in file_entries:
                print(p)

        # Hash: path + NUL + bytes + SOH
        for normalized_rel, full_path in file_entries:
            hasher.update(normalized_rel.encode("utf-8"))
            hasher.update(b"\x00")

            try:
                with open(full_path, "rb") as f:
                    while True:
                        chunk = f.read(8192)
                        if not chunk:
                            break
                        hasher.update(chunk)
            except OSError:
                if strict_read_errors:
                    raise
                hasher.update(b"__UNREADABLE__")

            hasher.update(b"\x01")

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
            backup_name = self.compute_directory_hash(path, debug=True)
        else:
            backup_name = os.path.basename(path)
        
        backup_path = os.path.join(self.backup_folder, backup_name)

        # If backup with this name already exists, return it (no duplicates)
        if os.path.exists(backup_path):
            print(f"Backup already exists: {backup_name}")
            return backup_path, backup_name

        # Create new backup
        if os.path.isfile(path):
            # Check if file should be skipped
            filename = os.path.basename(path)
            if should_skip_item(filename):
                raise ValueError(f"Cannot backup file that should be skipped: {filename}")
            # Backup single file
            shutil.copy2(path, backup_path)
            return backup_path, backup_name
            
        elif os.path.isdir(path):
            # Backup directory with filtering
            if recursive:
                copytree_filtered(path, backup_path, should_skip_item)
            else:
                # Non-recursive: create directory and copy only immediate files
                os.makedirs(backup_path, exist_ok=True)
                for item in os.listdir(path):
                    if should_skip_item(item):
                        continue
                    item_path = os.path.join(path, item)
                    if os.path.isfile(item_path):
                        shutil.copy2(item_path, os.path.join(backup_path, item))
            return backup_path, backup_name
        else:
            raise ValueError(f"Path {path} is not a file or directory")

    def restore_backup(self, backup_name: str, target_path: str = None):
        """
        Restore a backup to the target location, overwriting existing files.
        """
        backup_path = os.path.join(self.backup_folder, backup_name)

        if not os.path.exists(backup_path):
            raise ValueError(f"Backup {backup_name} does not exist")

        if target_path is None:
            target_path = backup_name

        # Ensure target directory exists and is empty (logic already exists in your file)
        if os.path.exists(target_path) and os.path.isdir(target_path):
            for filename in os.listdir(target_path):
                file_path = os.path.join(target_path, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f"Warning: Failed to delete {file_path}: {e}")
        else:
            os.makedirs(target_path, exist_ok=True)

        # Explicitly copy contents to avoid nesting
        if os.path.isfile(backup_path):
            shutil.copy2(backup_path, target_path)
        elif os.path.isdir(backup_path):
            for item in os.listdir(backup_path):
                s = os.path.join(backup_path, item)
                d = os.path.join(target_path, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
        
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