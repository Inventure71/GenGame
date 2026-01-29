#!/usr/bin/env python3
"""
Server-side file/patch/backup synchronization helpers.
"""

from __future__ import annotations

import glob
import importlib
import sys
import os
import json
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional

from BASE_files.BASE_menu_helpers import reload_game_code, load_settings
from BASE_files.transfer_manager import (
    server_request_backup_from_client,
    server_send_patch_file,
    server_send_file_chunks,
    server_send_backup_archive,
    server_handle_patch_chunk,
    server_handle_file_chunk,
    server_handle_backup_chunk,
    server_assemble_patch_file,
    server_assemble_client_backup,
    server_assemble_client_file,
)
from coding.non_callable_tools.version_control import VersionControl
from coding.tools.conflict_resolution import get_all_conflicts
from agent import auto_fix_conflicts


class ServerSyncManager:
    def __init__(self, server):
        self.server = server

    def load_game_files(self):
        """Load all Python files from GameFolder for synchronization."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        game_folder = os.path.join(project_root, "GameFolder")
        for root, _, files in os.walk(game_folder):
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    rel_path = os.path.relpath(filepath, project_root)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        self.server.game_files[rel_path] = content
                        print(f"Loaded game file: {rel_path}")
                    except Exception as e:
                        print(f"Failed to load {rel_path}: {e}")

    def restore_gamefolder_to_base(self):
        """Restore GameFolder to the base backup and clear module cache."""
        try:
            from coding.non_callable_tools.backup_handling import BackupHandler

            backup_handler = BackupHandler("__game_backups")
            backups = backup_handler.list_backups()

            if not backups:
                print("[warning] No backups available to restore from. GameFolder will remain in current state.")
                return

            backups_with_mtime = [(b, os.path.getmtime(os.path.join("__game_backups", b))) for b in backups]
            backups_with_mtime.sort(key=lambda x: x[1], reverse=True)
            base_backup = backups_with_mtime[0][0]

            print(f"Restoring GameFolder to base backup: {base_backup}")
            success, _ = backup_handler.restore_backup(base_backup, target_path="GameFolder")

            if success:
                print(f"[success] GameFolder restored to base backup: {base_backup}")

                modules_to_clear = [key for key in list(sys.modules.keys()) if key.startswith('GameFolder')]
                for module_name in modules_to_clear:
                    try:
                        del sys.modules[module_name]
                    except KeyError:
                        pass
                importlib.invalidate_caches()
                print(f"[success] Cleared {len(modules_to_clear)} cached GameFolder modules")

                self.load_game_files()

                merged_patch_path = os.path.join(self.server.server_patches_dir, "merged_patch.json")
                if os.path.exists(merged_patch_path):
                    os.remove(merged_patch_path)
                    print("[success] Cleared old merged_patch.json file")
            else:
                print(f"[warning] Failed to restore GameFolder to base backup: {base_backup}")
        except Exception as e:
            print(f"[error] Error restoring GameFolder to base backup: {e}")
            import traceback
            traceback.print_exc()

    def get_available_backups(self) -> set:
        """Get set of backup names server has available."""
        backup_dir = "__game_backups"
        if not os.path.exists(backup_dir):
            return set()
        return {d for d in os.listdir(backup_dir) if os.path.isdir(os.path.join(backup_dir, d))}

    def request_backup_from_client(self, player_id: str, backup_name: str):
        """Request backup transfer from client."""
        server_request_backup_from_client(self.server, player_id, backup_name)

    def initiate_game_start_with_patch_sync(self, patch_path: Optional[str] = None):
        """Generate and send merge patch to all clients, then wait for them to apply."""
        print("Initiating game start with patch synchronization...")

        if patch_path is None:
            patch_path = self.generate_merge_patch()

        if not patch_path or not os.path.exists(patch_path):
            print("No patches to merge or generation failed, starting game directly")
            self.notify_all_clients_game_start()
            return

        print(f"Sending merge patch to all clients: {patch_path}")
        self.server.waiting_for_patch_received = True
        self.server.clients_patch_received.clear()
        self.server.clients_patch_ready.clear()
        self.server.clients_patch_failed.clear()

        for player_id in self.server.clients.keys():
            self.send_patch_file(player_id, patch_path)

    def generate_merge_patch(self) -> Optional[str]:
        """Generate a single merge_patch.json from all patches in __patches directory."""
        patches_dir = os.path.join(os.path.dirname(__file__), "..", "__patches")

        if not os.path.exists(patches_dir):
            print("No __patches directory found")
            return None

        patch_files = [f for f in glob.glob(os.path.join(patches_dir, "*.json"))
                       if not f.endswith("merge_patch.json")]

        if not patch_files:
            print("No patch files found in __patches directory")
            return None

        if len(patch_files) == 1:
            print(f"Using single patch file: {os.path.basename(patch_files[0])}")
            return patch_files[0]

        print(f"[warning]  Found {len(patch_files)} patches:")
        for pf in patch_files:
            print(f"    - {os.path.basename(pf)}")
        print(f"[warning]  Using only first patch: {os.path.basename(patch_files[0])}")
        print(f"[warning]  TODO: Implement proper 3-way merge using VersionControl.merge_patches()")
        return patch_files[0]

    def send_patch_file(self, player_id: str, patch_file_path: str):
        """Send a patch file to a specific client."""
        server_send_patch_file(self.server, player_id, patch_file_path)

    def notify_all_clients_game_start(self):
        """Notify all connected clients to start the game."""
        print("Notifying all clients to start game...")
        self.server.clients_file_sync_ack.clear()

        message = {'type': 'game_start'}
        for player_id in self.server.clients.keys():
            try:
                self.server._send_message_to_client(player_id, message)
                print(f"Sent game_start to {player_id}")
            except Exception as e:
                print(f"Failed to send game_start to {player_id}: {e}")

    def notify_patch_sync_failed(self):
        """Notify all clients that patch synchronization failed and game cannot start."""
        print("Notifying all clients that patch sync failed...")

        failure_details = []
        for failed_player, error in self.server.clients_patch_failed.items():
            failure_details.append(f"{failed_player}: {error}")

        message = {
            'type': 'patch_sync_failed',
            'reason': 'One or more clients failed to apply the merge patch',
            'failed_clients': list(self.server.clients_patch_failed.keys()),
            'details': failure_details
        }

        for player_id in self.server.clients.keys():
            try:
                self.server._send_message_to_client(player_id, message)
                print(f"Sent patch_sync_failed notification to {player_id}")
            except Exception as e:
                print(f"Failed to send patch_sync_failed to {player_id}: {e}")

    def send_file_sync(self, player_id: str):
        """Send game files to client for synchronization."""
        message = {
            'type': 'file_sync',
            'files': self.server.game_files
        }
        try:
            self.server._send_message_to_client(player_id, message)
            print(f"Sent file sync to {player_id}")
        except Exception as e:
            print(f"Failed to send file sync to {player_id}: {e}")

    def handle_file_request(self, player_id: str, message: dict):
        """Handle a file request from a client."""
        file_path = message.get('file_path')

        if not file_path:
            print(f"Invalid file request from {player_id}: no file_path")
            return

        allowed_dirs = ['GameFolder', 'BASE_components']
        if not any(file_path.startswith(dir_name + '/') for dir_name in allowed_dirs):
            print(f"File request denied for {player_id}: {file_path} (not in allowed directories)")
            response = {
                'type': 'file_complete',
                'file_path': file_path,
                'success': False,
                'error': 'Access denied'
            }
            self.server._send_message_to_client(player_id, response)
            return

        project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        full_path = os.path.join(project_root, file_path)
        full_path = os.path.abspath(full_path)

        if not full_path.startswith(project_root):
            print(f"File request denied for {player_id}: {file_path} (outside project directory)")
            response = {
                'type': 'file_complete',
                'file_path': file_path,
                'success': False,
                'error': 'Access denied'
            }
            self.server._send_message_to_client(player_id, response)
            return

        if not os.path.exists(full_path):
            print(f"File not found for {player_id}: {file_path}")
            response = {
                'type': 'file_complete',
                'file_path': file_path,
                'success': False,
                'error': 'File not found'
            }
            self.server._send_message_to_client(player_id, response)
            return

        server_send_file_chunks(self.server, player_id, file_path, full_path)

    def get_server_patch_library_page(self, page: int, page_size: int, search: str = "") -> tuple[list, int]:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        base_dir = self.server.server_patches_dir
        if not os.path.isabs(base_dir):
            base_dir = os.path.join(project_root, base_dir)

        if not os.path.exists(base_dir):
            return [], 0

        search_term = (search or "").strip().lower()
        entries = []

        for root, _dirs, files in os.walk(base_dir):
            for file_name in files:
                if not file_name.endswith(".json"):
                    continue
                if file_name == "merged_patch.json":
                    continue
                full_path = os.path.join(root, file_name)
                rel_path = os.path.relpath(full_path, base_dir)
                parts = rel_path.split(os.sep)
                player_id = parts[0] if len(parts) > 1 else "unknown"
                patch_name = os.path.splitext(file_name)[0]

                if search_term:
                    if search_term not in patch_name.lower() and search_term not in player_id.lower():
                        continue

                try:
                    mtime = os.path.getmtime(full_path)
                except OSError:
                    mtime = 0.0

                entries.append((mtime, player_id, patch_name, full_path))

        entries.sort(key=lambda item: item[0], reverse=True)
        total = len(entries)
        start = max(0, page) * max(1, page_size)
        end = start + max(1, page_size)
        page_entries = entries[start:end]

        items = []
        for _mtime, player_id, patch_name, full_path in page_entries:
            base_backup = "Unknown"
            num_changes = 0
            try:
                with open(full_path, 'r') as f:
                    data = json.load(f)
                base_backup = data.get('name_of_backup', 'Unknown')
                changes = data.get('changes', [])
                num_changes = len(changes) if isinstance(changes, list) else 0
            except Exception:
                pass

            patch_id = f"{player_id}/{patch_name}"
            items.append({
                'patch_id': patch_id,
                'name': patch_name,
                'player_id': player_id,
                'base_backup': base_backup,
                'num_changes': num_changes
            })

        return items, total

    def send_patch_library_download(self, player_id: str, patch_id: str, include_backup: bool = True) -> None:
        if not patch_id:
            self.server._send_message_to_client(player_id, {
                'type': 'patch_library_error',
                'error': 'Missing patch_id'
            })
            return

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        base_dir = self.server.server_patches_dir
        if not os.path.isabs(base_dir):
            base_dir = os.path.join(project_root, base_dir)
        base_dir = os.path.abspath(base_dir)
        normalized = os.path.normpath(os.path.join(base_dir, patch_id))
        if not normalized.startswith(base_dir):
            self.server._send_message_to_client(player_id, {
                'type': 'patch_library_error',
                'error': 'Invalid patch_id'
            })
            return

        if not normalized.endswith(".json"):
            normalized = f"{normalized}.json"

        if not os.path.exists(normalized):
            self.server._send_message_to_client(player_id, {
                'type': 'patch_library_error',
                'error': f'Patch not found: {patch_id}'
            })
            return

        try:
            with open(normalized, 'rb') as f:
                patch_content = f.read()

            base_backup = "Unknown"
            try:
                with open(normalized, 'r') as f_text:
                    data = json.load(f_text)
                base_backup = data.get('name_of_backup', 'Unknown')
            except Exception:
                pass

            message = {
                'type': 'patch_library_file',
                'filename': os.path.basename(normalized),
                'content': patch_content,
                'patch_id': patch_id,
                'base_backup': base_backup
            }
            self.server._send_message_to_client(player_id, message)

            if include_backup and base_backup and base_backup != "Unknown":
                server_send_backup_archive(self.server, player_id, base_backup)
        except Exception as e:
            self.server._send_message_to_client(player_id, {
                'type': 'patch_library_error',
                'error': f'Failed to send patch: {e}'
            })

    def handle_file_chunk(self, player_id: str, message: dict):
        """Handle a file chunk received from a client."""
        server_handle_file_chunk(self.server, player_id, message)

    def handle_backup_chunk(self, player_id: str, message: dict):
        """Handle a backup file chunk received from a client."""
        server_handle_backup_chunk(self.server, player_id, message)

    def assemble_client_backup(self, player_id: str, backup_name: str) -> bool:
        """Assemble a complete backup from client chunks and extract it."""
        return server_assemble_client_backup(self.server, player_id, backup_name)

    def assemble_client_file(self, player_id: str, file_path: str):
        """Assemble a complete file from client chunks."""
        server_assemble_client_file(self.server, player_id, file_path)

    def handle_patch_chunk(self, player_id: str, message: dict):
        """Handle incoming patch file chunk from client."""
        server_handle_patch_chunk(self.server, player_id, message)

    def assemble_patch_file(self, player_id: str, patch_name: str):
        """Assemble complete patch file from chunks."""
        server_assemble_patch_file(self.server, player_id, patch_name)

    def merge_and_distribute_patches(self):
        """
        Merge all patches from all clients with retry logic.
        Uses auto_fix_conflicts if there are merge conflicts.
        """
        print("\n" + "="*60)
        print("STARTING PATCH MERGE PROCESS")
        print("="*60)

        all_patches_info = list(self.server.client_patches.values())
        compatible, error = self.validate_base_backup_compatibility(all_patches_info)

        if not compatible:
            print(f"[error] Base backup validation failed: {error}")
            self.notify_patch_merge_failed(f"Incompatible patches: {error}")
            return

        print("[success] Base backup validation passed")

        required_backup = None
        if all_patches_info and all_patches_info[0]:
            required_backup = all_patches_info[0][0].get('base_backup')

        if required_backup:
            available_backups = self.get_available_backups()
            if required_backup not in available_backups:
                print(f"[warning]  Server missing backup '{required_backup}', requesting from client")
                requesting_client = None
                for client_id, backup_name in self.server.client_backups.items():
                    if backup_name == required_backup:
                        requesting_client = client_id
                        break

                if requesting_client:
                    print(f"🔄 BACKUP TRANSFER: Server missing backup '{required_backup}', requesting from client '{requesting_client}'")

                    self.server.backup_transfer_in_progress = True
                    self.server.backup_transfer_client = requesting_client
                    self.server.backup_transfer_name = required_backup
                    self.server.backup_transfer_start_time = time.time()
                    self.server.backup_transfer_complete_event = threading.Event()
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] 🔧 DEBUG: Backup transfer setup - client: {requesting_client}, backup: {required_backup}, event created")

                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] 📨 DEBUG: About to request backup {required_backup} from client {requesting_client}")
                    self.request_backup_from_client(requesting_client, required_backup)
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] 📤 BACKUP TRANSFER: Sent request to {requesting_client} for backup '{required_backup}'")
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] 🎪 DEBUG: backup_transfer_in_progress: {self.server.backup_transfer_in_progress}, event exists: {hasattr(self.server, 'backup_transfer_complete_event')}")
                    print("⏳ BACKUP TRANSFER: Waiting for backup transfer (30s timeout)...")

                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] ⏳ DEBUG: Starting to wait for backup transfer event (30s timeout)")
                    if not self.server.backup_transfer_complete_event.wait(timeout=30.0):
                        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                        print(f"[{timestamp}] [error] BACKUP TRANSFER: TIMEOUT - Backup '{required_backup}' not received within 30 seconds")
                        self.notify_patch_merge_failed(f"Backup transfer timeout for '{required_backup}'")
                        return

                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] [success] DEBUG: Backup transfer event received - proceeding with merge")
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] [success] BACKUP TRANSFER: Successfully received backup '{required_backup}'")
                else:
                    print(f"[error] No client has backup '{required_backup}'")
                    self.notify_patch_merge_failed(f"Required backup '{required_backup}' not available")
                    return

        all_patch_paths = []
        for player_id, patches_info in self.server.client_patches.items():
            for patch_info in patches_info:
                patch_name = patch_info['name']
                patch_path = os.path.join(self.server.server_patches_dir, player_id, f"{patch_name}.json")
                if os.path.exists(patch_path):
                    all_patch_paths.append(patch_path)

        print(f"Found {len(all_patch_paths)} patch files to merge")

        if len(all_patch_paths) == 0:
            print("No patches to merge, starting game directly")
            self.notify_all_clients_game_start()
            return

        os.makedirs(self.server.server_patches_dir, mode=0o755, exist_ok=True)
        output_path = os.path.join(self.server.server_patches_dir, "merged_patch.json")
        success = False

        for attempt in range(3):
            print(f"\n--- Merge Attempt {attempt + 1}/3 ---")

            success, result = self.merge_patches_iteratively(all_patch_paths, output_path)

            if success:
                print(f"[success] Merge successful on attempt {attempt + 1}")
                break
            print(f"[warning]  Merge had conflicts: {result}")

            print("Running auto_fix_conflicts...")
            try:
                settings = {}
                settings_dict = load_settings()
                if settings_dict.get("success"):
                    settings["selected_provider"] = settings_dict.get("selected_provider", "GEMINI")
                    if settings["selected_provider"] == "GEMINI":
                        settings["api_key"] = settings_dict.get("gemini_api_key", "")
                    elif settings["selected_provider"] == "OPENAI":
                        settings["api_key"] = settings_dict.get("openai_api_key", "")
                    else:
                        print("WARNING: Invalid provider, using default settings")
                        success = False
                        break
                    settings["model_name"] = settings_dict.get("model", "models/gemini-3-flash-preview")
                else:
                    print("WARNING: No settings found, NO API KEY --> NO AUTO-FIX")
                    success = False
                    break

                base_backup_name = all_patches_info[0][0].get('base_backup', 'Unknown')
                auto_fix_conflicts(settings, output_path, patch_paths=all_patch_paths, base_backup=base_backup_name)

                remaining_conflicts = get_all_conflicts(output_path)
                if len(remaining_conflicts) == 0:
                    print("[success] Auto-fix resolved all conflicts!")
                    success = True
                    break
                print(f"[warning]  {len(remaining_conflicts)} conflicts remain after auto-fix")
            except Exception as e:
                print(f"[error] Auto-fix failed: {e}")

        if not success:
            print("\n[error] MERGE FAILED AFTER 3 ATTEMPTS")
            self.notify_patch_merge_failed("Patches are incompatible - could not resolve conflicts after 3 attempts")
            return

        print("\n[success] MERGE SUCCESSFUL - Applying to server")

        self._normalize_seed_in_merged_patch(output_path)

        try:
            vc = VersionControl()
            vc.apply_all_changes(
                needs_rebase=True,
                path_to_BASE_backup="__game_backups",
                file_containing_patches=output_path,
                skip_warnings=True
            )
            self.server.arena = None
            reloaded_setup = reload_game_code()
            
            if reloaded_setup:
                from GameFolder.setup import setup_battle_arena
                print("[success] Server GameFolder modules deep reloaded with merged patches")
            else:
                print("[warning] Server GameFolder reload failed, may use old code")

            self.load_game_files()

            self.server.arena = None
            print("[success] Server GameFolder updated with merged patches")
        except Exception as e:
            print(f"[error] Failed to apply patches to server: {e}")
            self.notify_patch_merge_failed(f"Server patch application failed: {e}")
            return

        print("Distributing to clients")

        self.initiate_game_start_with_patch_sync(output_path)

    def _normalize_seed_in_merged_patch(self, patch_path: str) -> bool:
        """
        Normalize all random.seed() values in setup.py to a single random value.
        This ensures all clients receive the same seed value in the merged patch.
        Only normalizes the NEW seed value (in + lines), keeping the OLD value (in - lines)
        so the patch can still match against the base backup.
        """
        import json
        import random
        import re

        try:
            with open(patch_path, 'r', encoding='utf-8') as f:
                patch_data = json.load(f)

            normalized_seed =  int(datetime.now().timestamp())


            any_modified = False
            for change in patch_data.get("changes", []):
                if change.get("path", "").endswith("setup.py"):
                    diff = change.get("diff", "")
                    pattern = r'random\.seed\(\s*\d+\s*\)'
                    
                    # Only replace seeds in addition lines (+), not deletion lines (-)
                    # This preserves the old seed value so the patch can match the base backup
                    lines = diff.split('\n')
                    new_lines = []
                    change_modified = False
                    for line in lines:
                        if line.startswith('+') and re.search(pattern, line):
                            # Normalize seed in addition lines only
                            new_line = re.sub(pattern, f'random.seed({normalized_seed})', line)
                            new_lines.append(new_line)
                            change_modified = True
                            any_modified = True
                        else:
                            new_lines.append(line)
                    
                    if change_modified:
                        change["diff"] = '\n'.join(new_lines)
                        print(f"    ✓ Normalized random.seed() to {normalized_seed} in merged patch")

            if any_modified:
                with open(patch_path, 'w', encoding='utf-8') as f:
                    json.dump(patch_data, f, indent=2, ensure_ascii=False)
                print(f"[success] Normalized all seed values in merged patch to {normalized_seed}")
                return True
        except Exception as e:
            print(f"[warning] Could not normalize seed in merged patch: {e}")
            import traceback
            traceback.print_exc()

        return False

    def validate_base_backup_compatibility(self, all_patches_info: List[List[Dict]]) -> tuple:
        """Validate that all patches use the same base backup."""
        all_base_backups = set()

        for client_patches in all_patches_info:
            for patch_info in client_patches:
                all_base_backups.add(patch_info.get('base_backup', 'Unknown'))

        if len(all_base_backups) == 0:
            return True, None

        if len(all_base_backups) > 1:
            return False, f"Different base backups: {', '.join(all_base_backups)}"

        return True, None

    def merge_patches_iteratively(self, patch_paths: List[str], output_path: str) -> tuple:
        """
        Merge multiple patches iteratively: merge(merge(A, B), C), etc.
        Returns (success, result_message)
        """
        if len(patch_paths) == 0:
            return False, "No patches to merge"

        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, mode=0o755, exist_ok=True)

        if len(patch_paths) == 1:
            import shutil
            try:
                shutil.copy(patch_paths[0], output_path)
            except PermissionError:
                os.makedirs(output_dir, mode=0o755, exist_ok=True)
                if os.path.exists(output_path):
                    try:
                        os.chmod(output_path, 0o644)
                    except Exception:
                        os.remove(output_path)
                shutil.copy(patch_paths[0], output_path)
            return True, "Single patch copied"

        import json
        with open(patch_paths[0], 'r') as f:
            data = json.load(f)
            _base_backup_name = data.get('name_of_backup', 'Unknown')

        vc = VersionControl()

        current_output = output_path
        success, result = vc.merge_patches(
            base_backup_path="__game_backups",
            patch_a_path=patch_paths[0],
            patch_b_path=patch_paths[1],
            output_path=current_output
        )

        if not success and "conflicts" not in result.lower():
            return False, result

        for i in range(2, len(patch_paths)):
            temp_output = output_path + f".temp{i}"

            success, result = vc.merge_patches(
                base_backup_path="__game_backups",
                patch_a_path=current_output,
                patch_b_path=patch_paths[i],
                output_path=temp_output
            )

            import shutil
            shutil.move(temp_output, current_output)

            if not success and "conflicts" not in result.lower():
                return False, result

        conflicts = get_all_conflicts(current_output)
        if len(conflicts) > 0:
            return False, f"Merge completed with {len(conflicts)} file(s) having conflicts"

        return True, "Merge successful"

    def notify_patch_merge_failed(self, reason: str):
        """Notify all clients that patch merge failed."""
        print(f"Notifying clients: {reason}")

        message = {
            'type': 'patch_merge_failed',
            'reason': reason
        }

        for player_id in self.server.clients.keys():
            try:
                self.server._send_message_to_client(player_id, message)
            except Exception as e:
                print(f"Failed to notify {player_id}: {e}")

        self.server.clients_ready_status.clear()
        self.server.client_patches.clear()
