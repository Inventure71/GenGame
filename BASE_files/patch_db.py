import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

class PatchDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create patches table
        # game_folder_hash is used for deduplication
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS patches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_folder_hash TEXT NOT NULL,
            patch_hash TEXT NOT NULL,
            backup_name TEXT,
            prompt_used TEXT,
            patch_changes TEXT NOT NULL,
            creator_name TEXT,
            created_at TEXT,
            name TEXT
        )
        ''')
        
        # Create index on game_folder_hash for fast lookups/deduplication
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_game_folder_hash ON patches (game_folder_hash)')
        
        conn.commit()
        conn.close()

    def insert_patch(self, 
                     game_folder_hash: str, 
                     patch_hash: str, 
                     backup_name: str, 
                     prompt_used: str, 
                     patch_changes: List[Dict], 
                     creator_name: str = "Unknown",
                     name: str = "Untitled Patch") -> Tuple[bool, str]:
        """
        Insert a patch into the database.
        Returns (success, message).
        If a patch with the same game_folder_hash exists, it updates the existing entry (deduplication).
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check for existing patch with same game_folder_hash
            cursor.execute('SELECT id FROM patches WHERE game_folder_hash = ?', (game_folder_hash,))
            existing = cursor.fetchone()
            
            patch_changes_json = json.dumps(patch_changes)
            timestamp = datetime.now().isoformat()
            
            if existing:
                patch_id = existing[0]
                # Update existing patch
                cursor.execute('''
                UPDATE patches SET 
                    patch_hash = ?,
                    backup_name = ?,
                    prompt_used = ?,
                    patch_changes = ?,
                    creator_name = ?,
                    created_at = ?,
                    name = ?
                WHERE id = ?
                ''', (patch_hash, backup_name, prompt_used, patch_changes_json, creator_name, timestamp, name, patch_id))
                conn.commit()
                conn.close()
                return True, f"Updated existing patch (ID: {patch_id})"
            else:
                # Insert new patch
                cursor.execute('''
                INSERT INTO patches (game_folder_hash, patch_hash, backup_name, prompt_used, patch_changes, creator_name, created_at, name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (game_folder_hash, patch_hash, backup_name, prompt_used, patch_changes_json, creator_name, timestamp, name))
                conn.commit()
                conn.close()
                return True, "Inserted new patch"
                
        except Exception as e:
            return False, f"Database error: {str(e)}"

    def get_patches(self, page: int = 0, page_size: int = 50, search: str = "") -> Tuple[List[Dict], int]:
        """
        Get a paginated list of patches.
        Returns (list of patches, total_count).
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM patches"
            params = []
            
            if search:
                query += " WHERE name LIKE ? OR creator_name LIKE ? OR prompt_used LIKE ?"
                search_term = f"%{search}%"
                params.extend([search_term, search_term, search_term])
                
            # Get total count first
            count_query = f"SELECT COUNT(*) FROM ({query})"
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]
            
            # Get page data
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([page_size, page * page_size])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            patches = []
            for row in rows:
                patch_dict = dict(row)
                # We don't parse patch_changes for the list view to save perf, 
                # but we calculate num_changes
                try:
                    changes = json.loads(patch_dict['patch_changes'])
                    patch_dict['num_changes'] = len(changes)
                except:
                    patch_dict['num_changes'] = 0
                del patch_dict['patch_changes'] # Don't send full blob in list
                patches.append(patch_dict)
                
            conn.close()
            return patches, total
            
        except Exception as e:
            print(f"Error getting patches: {e}")
            return [], 0

    def get_patch_by_id(self, patch_id: int) -> Optional[Dict]:
        """Get full patch details by ID."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM patches WHERE id = ?", (patch_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                patch = dict(row)
                patch['patch_changes'] = json.loads(patch['patch_changes'])
                return patch
            return None
            
        except Exception as e:
            print(f"Error getting patch {patch_id}: {e}")
            return None
            
    def get_patch_payload(self, patch_id: int) -> Optional[Dict]:
        """
        Get the dictionary required to reconstruct the .json file.
        Returns dict with keys: name_of_backup, prompt_used, changes, game_folder_hash, patch_hash
        """
        patch = self.get_patch_by_id(patch_id)
        if patch:
            return {
                "name_of_backup": patch['backup_name'],
                "prompt_used": patch['prompt_used'],
                "changes": patch['patch_changes'],
                "game_folder_hash": patch['game_folder_hash'],
                "patch_hash": patch['patch_hash']
            }
        return None

    def delete_patch(self, patch_id: int) -> bool:
        """Delete a patch by ID."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM patches WHERE id = ?", (patch_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error deleting patch {patch_id}: {e}")
            return False
