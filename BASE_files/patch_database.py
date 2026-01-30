import os
import sqlite3
import json
import time
from typing import List, Dict, Tuple, Optional

# Default DB path: inside __patches so it can live on an external volume (single source of truth)
DEFAULT_PATCHES_DIR = "__patches"
DEFAULT_DB_FILENAME = "server_patches.db"


def get_default_db_path() -> str:
    """Return the default patch database path and ensure its directory exists."""
    path = os.path.join(DEFAULT_PATCHES_DIR, DEFAULT_DB_FILENAME)
    dir_path = os.path.dirname(path)
    if dir_path:
        os.makedirs(dir_path, mode=0o755, exist_ok=True)
    return os.path.abspath(path)


class PatchDatabase:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None or db_path == "":
            db_path = get_default_db_path()
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database and tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS patches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    hash_result TEXT UNIQUE,
                    hash_patch TEXT,
                    backup_name TEXT,
                    prompt_used TEXT,
                    patch_changes TEXT,
                    creator_name TEXT,
                    created_at REAL
                )
            ''')
            
            # Check if name column exists (in case table was created before name was added)
            cursor.execute("PRAGMA table_info(patches)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'name' not in columns:
                cursor.execute("ALTER TABLE patches ADD COLUMN name TEXT")
                
            conn.commit()

    def add_patch(self, patch_data: Dict, creator_name: str, patch_hash: str, name: str = None) -> int:
        """
        Add a patch to the database.
        Returns the ID of the new or existing patch.
        """
        hash_result = patch_data.get("game_hash")
        # If no game_hash provided (legacy patch), use patch_hash as fallback for uniqueness
        if not hash_result:
            hash_result = f"LEGACY_{patch_hash}"

        backup_name = patch_data.get("name_of_backup", "Unknown")
        prompt_used = patch_data.get("prompt_used", "")
        patch_changes = json.dumps(patch_data.get("changes", []))
        created_at = time.time()
        
        if not name:
            # Extract name from prompt if not provided
            name = prompt_used.split('\n')[0][:50] if prompt_used else "Unnamed Patch"
            if ':' in name:
                name = name.split(':', 1)[0]
            name = name.strip() or "Unnamed Patch"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check for existing patch with same result hash
            cursor.execute("SELECT id FROM patches WHERE hash_result = ?", (hash_result,))
            row = cursor.fetchone()
            if row:
                return row[0]

            cursor.execute('''
                INSERT INTO patches (name, hash_result, hash_patch, backup_name, prompt_used, patch_changes, creator_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, hash_result, patch_hash, backup_name, prompt_used, patch_changes, creator_name, created_at))
            
            return cursor.lastrowid

    def get_patch_by_id(self, patch_id: int) -> Optional[Dict]:
        """Retrieve a patch by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM patches WHERE id = ?", (patch_id,))
            row = cursor.fetchone()
            
            if row:
                patch_data = dict(row)
                # Parse JSON changes back to list
                try:
                    patch_data['changes'] = json.loads(patch_data['patch_changes'])
                except:
                    patch_data['changes'] = []
                del patch_data['patch_changes']
                
                # Reconstruct full patch object format (include name for display/send)
                return {
                    'id': row['id'],
                    'name': row['name'] if row['name'] is not None else f"Patch_{row['id']}",
                    'game_hash': row['hash_result'],
                    'name_of_backup': row['backup_name'],
                    'prompt_used': row['prompt_used'],
                    'changes': patch_data['changes'],
                    'creator_name': row['creator_name'],
                    'created_at': row['created_at']
                }
            return None

    def get_patches_page(self, page: int, page_size: int, search: str = "") -> Tuple[List[Dict], int]:
        """
        Get a page of patches.
        Returns (items, total_count).
        """
        offset = page * page_size
        search_term = f"%{search}%" if search else "%"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get total count (same filter as SELECT for consistent paging)
            cursor.execute('''
                SELECT COUNT(*) FROM patches 
                WHERE name LIKE ? OR prompt_used LIKE ? OR creator_name LIKE ? OR backup_name LIKE ?
            ''', (search_term, search_term, search_term, search_term))
            total = cursor.fetchone()[0]
            
            # Get items
            cursor.execute('''
                SELECT id, name, hash_result, backup_name, prompt_used, creator_name, created_at, 
                       (length(patch_changes) - length(replace(patch_changes, 'path', ''))) / 4 as num_changes
                FROM patches
                WHERE name LIKE ? OR prompt_used LIKE ? OR creator_name LIKE ? OR backup_name LIKE ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (search_term, search_term, search_term, search_term, page_size, offset))
            
            items = []
            for row in cursor.fetchall():
                items.append({
                    'patch_id': str(row['id']), # Use ID as patch_id
                    'name': row['name'],
                    'player_id': row['creator_name'],
                    'base_backup': row['backup_name'],
                    'num_changes': row['num_changes'], # Approx count
                    'game_hash': row['hash_result'],
                    'created_at': row['created_at']
                })
                
            return items, total

    def delete_patch(self, patch_id: int) -> bool:
        """Delete a patch by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM patches WHERE id = ?", (patch_id,))
            return cursor.rowcount > 0

    def get_patch_by_name_and_creator(self, name: str, creator_name: str) -> Optional[Dict]:
        """Find a specific patch by name and creator."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM patches 
                WHERE name = ? AND creator_name = ?
                ORDER BY created_at DESC LIMIT 1
            ''', (name, creator_name))
            row = cursor.fetchone()
            if row:
                return self.get_patch_by_id(row['id'])
            return None

    def get_all_patch_ids(self) -> List[int]:
        """Return all patch IDs in the database (for export)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM patches ORDER BY id ASC")
            return [row[0] for row in cursor.fetchall()]
