"""
Simple Conflict Resolution Cache

Caches resolved conflicts based on conflict content hash + base backup.
Extremely simple and fast - just stores conflict resolutions by conflict signature.
"""

import json
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional


class ConflictCache:
    """Simple cache for conflict resolutions."""

    def __init__(self, cache_file: str = "__server_patches/conflict_cache.json"):
        self.cache_file = Path(cache_file)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_cache(self):
        """Save cache to disk."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save cache: {e}")

    def get_conflict_hash(self, option_a: str, option_b: str) -> str:
        """Generate hash for a conflict based on its content."""
        content = f"{option_a}||||{option_b}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get_resolution(self, conflict_hash: str, base_backup: str) -> Optional[Dict]:
        """
        Get cached resolution for a conflict.

        Returns resolution dict if found, None otherwise.
        Checks exact backup match first, then any backup as fallback.
        """
        # First try exact backup match
        cache_key = f"{conflict_hash}:{base_backup}"
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            entry["uses"] = entry.get("uses", 0) + 1
            self._save_cache()
            return entry["resolution"]

        # Then try any backup (but mark as fallback)
        fallback_key = f"{conflict_hash}:*"
        if fallback_key in self.cache:
            entry = self.cache[fallback_key]
            entry["uses"] = entry.get("uses", 0) + 1
            self._save_cache()
            return entry["resolution"]

        return None

    def store_resolution(self, conflict_hash: str, base_backup: str, resolution: Dict):
        """Store a conflict resolution."""
        # Store with exact backup
        exact_key = f"{conflict_hash}:{base_backup}"
        self.cache[exact_key] = {
            "resolution": resolution,
            "backup": base_backup,
            "created": time.time(),
            "uses": 0
        }

        # Also store as fallback (any backup)
        fallback_key = f"{conflict_hash}:*"
        if fallback_key not in self.cache:  # Only if not already exists
            self.cache[fallback_key] = {
                "resolution": resolution,
                "backup": "any",
                "created": time.time(),
                "uses": 0
            }

        self._save_cache()

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total_entries = len(self.cache)
        total_uses = sum(entry.get("uses", 0) for entry in self.cache.values())

        exact_matches = sum(1 for key in self.cache.keys() if not key.endswith(":*"))
        fallback_matches = sum(1 for key in self.cache.keys() if key.endswith(":*"))

        return {
            "total_entries": total_entries,
            "exact_matches": exact_matches,
            "fallback_matches": fallback_matches,
            "total_uses": total_uses
        }

    def get_merged_patch(self, combined_hash: str) -> Optional[Dict]:
        """Get a cached merged patch for a combination of input patches."""
        merged_key = f"merged_patch:{combined_hash}"
        if merged_key in self.cache:
            entry = self.cache[merged_key]
            entry["uses"] = entry.get("uses", 0) + 1
            self._save_cache()
            return entry["patch"]
        return None

    def store_merged_patch(self, combined_hash: str, patch: Dict):
        """Store a successfully merged patch."""
        merged_key = f"merged_patch:{combined_hash}"
        self.cache[merged_key] = {
            "patch": patch,
            "timestamp": time.time(),
            "uses": 0
        }
        self._save_cache()

    def clear(self):
        """Clear all cache entries."""
        self.cache = {}
        self._save_cache()


# Global instance
_cache = None

def get_conflict_cache() -> ConflictCache:
    """Get the global conflict cache instance."""
    global _cache
    if _cache is None:
        _cache = ConflictCache()
    return _cache


def try_apply_cached_conflicts(patch_path: str, base_backup: str) -> int:
    """
    Try to resolve conflicts in a patch using cached resolutions.

    Returns number of conflicts resolved from cache.
    """
    from coding.tools.conflict_resolution import get_all_conflicts, resolve_conflict

    conflicts = get_all_conflicts(patch_path)
    if not conflicts:
        return 0

    cache = get_conflict_cache()
    resolved_count = 0

    for file_path, file_conflicts in conflicts.items():
        for conflict in file_conflicts:
            conflict_hash = cache.get_conflict_hash(conflict["option_a"], conflict["option_b"])
            cached_resolution = cache.get_resolution(conflict_hash, base_backup)

            if cached_resolution:
                try:
                    # Apply the cached resolution
                    if "resolution" in cached_resolution:
                        resolve_conflict(
                            patch_path=patch_path,
                            file_path=file_path,
                            conflict_num=conflict["conflict_num"],
                            resolution=cached_resolution["resolution"]
                        )
                    elif "manual_content" in cached_resolution:
                        resolve_conflict(
                            patch_path=patch_path,
                            file_path=file_path,
                            conflict_num=conflict["conflict_num"],
                            manual_content=cached_resolution["manual_content"]
                        )

                    resolved_count += 1
                    print(f"[success] Applied cached resolution for conflict {conflict['conflict_num']} in {file_path}")

                except Exception as e:
                    # If cached resolution fails, don't use it again for this conflict
                    print(f"[warning]  Cached resolution failed for conflict {conflict['conflict_num']}: {e}")
                    # Remove the failing cached entry
                    cache_key = f"{conflict_hash}:{base_backup}"
                    if cache_key in cache.cache:
                        del cache.cache[cache_key]
                        cache._save_cache()

    return resolved_count
