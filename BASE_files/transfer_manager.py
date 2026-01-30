"""
Shared transfer utilities for patch/backup/file transfers.
This centralizes chunking, assembly, and archive helpers to avoid duplication.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional
import io
import os
import tarfile
import tempfile
import time
import json
import hashlib
from datetime import datetime

from coding.non_callable_tools.backup_handling import BackupHandler


# ---------------------------
# Core chunking helpers
# ---------------------------

def queue_chunked_file(
    outgoing_queue: list,
    file_path: str,
    message_factory: Callable[[int, int, bytes], dict],
    on_chunk: Optional[Callable[[int, int, bytes], None]] = None,
    chunk_size: int = 64 * 1024,
    file_size: Optional[int] = None,
) -> int:
    """Queue a file for transfer in chunks and return total_chunks."""
    if file_size is None:
        file_size = os.path.getsize(file_path)
    
    # Ensure at least 1 chunk is sent even for empty files to trigger file creation on server
    total_chunks = max(1, (file_size + chunk_size - 1) // chunk_size)

    with open(file_path, 'rb') as f:
        for chunk_num in range(total_chunks):
            chunk_data = f.read(chunk_size)
            message = message_factory(chunk_num, total_chunks, chunk_data)
            outgoing_queue.append(message)
            if on_chunk:
                on_chunk(chunk_num, total_chunks, chunk_data)

    return total_chunks


@dataclass
class ChunkTransfer:
    chunks: Dict[int, bytes] = field(default_factory=dict)
    total_chunks: int = 0
    received_chunks: int = 0
    start_time: float = field(default_factory=time.time)


# ---------------------------
# Client-side helpers
# ---------------------------

def client_send_patch_file(outgoing_queue: list, file_path: str, patch_name: str, player_id: str) -> int:
    """Send a patch file to server in chunks. Returns total_chunks."""
    def message_factory(chunk_num: int, total_chunks: int, chunk_data: bytes) -> dict:
        return {
            'type': 'patch_chunk',
            'patch_name': patch_name,
            'chunk_num': chunk_num,
            'total_chunks': total_chunks,
            'data': chunk_data,
            'player_id': player_id
        }

    total_chunks = queue_chunked_file(outgoing_queue, file_path, message_factory)
    return total_chunks


def _create_backup_archive(backup_path: str) -> str:
    """Create a temporary tar.gz archive for a backup directory and return its path."""
    with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as temp_file:
        temp_path = temp_file.name

    with tarfile.open(temp_path, 'w:gz') as tar:
        tar.add(backup_path, arcname=os.path.basename(backup_path))

    return temp_path


def client_send_backup(
    outgoing_queue: list,
    backup_name: str,
    debug_logging: bool = False,
) -> Optional[int]:
    """Send a backup folder to the server. Returns total_chunks or None on failure."""
    try:
        cwd = os.getcwd()
        print(f"BACKUP SEND: Current working directory: {cwd}")

        backup_path = f"__game_backups/{backup_name}"
        abs_backup_path = os.path.abspath(backup_path)
        print(f"BACKUP SEND: Looking for backup at: {abs_backup_path}")

        if not os.path.exists(backup_path):
            print(f"[error] BACKUP SEND: Backup {backup_name} not found locally at {backup_path}")
            print(f"[error] BACKUP SEND: Absolute path: {abs_backup_path}")
            game_backups_dir = "__game_backups"
            if os.path.exists(game_backups_dir):
                contents = os.listdir(game_backups_dir)
                print(f"[error] BACKUP SEND: Contents of __game_backups: {contents}")
            else:
                print(f"[error] BACKUP SEND: __game_backups directory does not exist")
            return None

        print(f"[success] BACKUP SEND: Found backup '{backup_name}' at {backup_path}")
        print(f"BACKUP SEND: Starting to send backup '{backup_name}' from {backup_path}")

        temp_path = _create_backup_archive(backup_path)

        chunk_size = 64 * 1024
        file_size = os.path.getsize(temp_path)
        total_chunks = (file_size + chunk_size - 1) // chunk_size

        print(f"BACKUP SEND: Compressed '{backup_name}' to {file_size} bytes, will send in {total_chunks} chunks")

        def message_factory(chunk_num: int, total_chunks: int, chunk_data: bytes) -> dict:
            return {
                'type': 'file_chunk',
                'backup_name': backup_name,
                'chunk_num': chunk_num,
                'total_chunks': total_chunks,
                'data': chunk_data,
                'is_backup': True
            }

        def on_chunk(chunk_num: int, total_chunks: int, chunk_data: bytes) -> None:
            progress = (chunk_num + 1) / total_chunks * 100
            if debug_logging:
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{timestamp}] BACKUP SEND: Queued chunk {chunk_num+1}/{total_chunks} ({progress:.1f}%) for '{backup_name}' - data size: {len(chunk_data)} bytes")

        queue_chunked_file(
            outgoing_queue,
            temp_path,
            message_factory,
            on_chunk=on_chunk,
            chunk_size=chunk_size,
            file_size=file_size,
        )

        print(f"[success] BACKUP SEND: Successfully queued all {total_chunks} chunks for backup '{backup_name}' to server")

        os.unlink(temp_path)
        return total_chunks

    except Exception as e:
        print(f"[error] BACKUP SEND: Failed to send backup {backup_name}: {e}")
        return None


def client_send_file(
    outgoing_queue: list,
    file_path: str,
    target_path: str,
    player_id: Optional[str] = None,
    on_progress: Optional[Callable[[str, float, str], None]] = None,
) -> bool:
    """Send a generic file to the server."""
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return False

    def message_factory(chunk_num: int, total_chunks: int, chunk_data: bytes) -> dict:
        payload = {
            'type': 'file_chunk',
            'file_path': target_path,
            'chunk_num': chunk_num,
            'total_chunks': total_chunks,
            'data': chunk_data,
        }
        if player_id:
            payload['player_id'] = player_id
        return payload

    def on_chunk(chunk_num: int, total_chunks: int, _chunk_data: bytes) -> None:
        if on_progress:
            progress = (chunk_num + 1) / total_chunks
            on_progress(target_path, progress, 'sending')

    queue_chunked_file(outgoing_queue, file_path, message_factory, on_chunk=on_chunk)
    return True


def client_handle_file_chunk(
    message: dict,
    file_transfers: Dict[str, dict],
    outgoing_queue: list,
    player_id: str,
    on_file_received: Optional[Callable[[str, bool], None]] = None,
    on_file_transfer_progress: Optional[Callable[[str, float, str], None]] = None,
) -> None:
    """Handle incoming file chunks and assemble when complete."""
    file_path = message['file_path']
    chunk_num = message['chunk_num']
    total_chunks = message['total_chunks']
    chunk_data = message['data']

    if file_path not in file_transfers:
        file_transfers[file_path] = {
            'chunks': {},
            'total_chunks': total_chunks,
            'received_chunks': 0,
            'start_time': time.time()
        }

    transfer = file_transfers[file_path]

    if chunk_num not in transfer['chunks']:
        transfer['chunks'][chunk_num] = chunk_data
        transfer['received_chunks'] += 1

        if on_file_transfer_progress:
            progress = transfer['received_chunks'] / total_chunks
            on_file_transfer_progress(file_path, progress, 'receiving')

    if transfer['received_chunks'] == total_chunks:
        _client_assemble_file(file_transfers, file_path, outgoing_queue, player_id, on_file_received)


def _client_queue_file_ack(outgoing_queue: list, player_id: str, file_path: str, success: bool, error: Optional[str] = None) -> None:
    message = {
        'type': 'file_ack',
        'file_path': file_path,
        'player_id': player_id,
        'success': success
    }
    if error:
        message['error'] = error
    outgoing_queue.append(message)


def _client_assemble_file(
    file_transfers: Dict[str, dict],
    file_path: str,
    outgoing_queue: list,
    player_id: str,
    on_file_received: Optional[Callable[[str, bool], None]] = None,
) -> None:
    transfer = file_transfers[file_path]

    try:
        dir_name = os.path.dirname(file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        with open(file_path, 'wb') as f:
            for chunk_num in range(transfer['total_chunks']):
                if chunk_num in transfer['chunks']:
                    f.write(transfer['chunks'][chunk_num])
                else:
                    raise ValueError(f"Missing chunk {chunk_num} for file {file_path}")

        _client_queue_file_ack(outgoing_queue, player_id, file_path, True)

        if on_file_received:
            on_file_received(file_path, True)

        print(f"File received successfully: {file_path}")

    except Exception as e:
        print(f"Failed to assemble file {file_path}: {e}")

        _client_queue_file_ack(outgoing_queue, player_id, file_path, False, str(e))

        if on_file_received:
            on_file_received(file_path, False)

    finally:
        if file_path in file_transfers:
            del file_transfers[file_path]


def client_handle_patch_file(
    message: dict,
    patch_dir: str,
    send_patch_received: Callable[[], None],
    send_patch_applied: Callable[[bool, Optional[str]], None],
    on_patch_received: Optional[Callable[[str], None]] = None,
) -> None:
    """Handle incoming patch file from server."""
    filename = message.get('filename', 'merge_patch.json')
    content = message.get('content', b'')

    print(f"Received patch file: {filename} ({len(content)} bytes)")

    os.makedirs(patch_dir, exist_ok=True)
    patch_path = os.path.join(patch_dir, filename)

    try:
        with open(patch_path, 'wb') as f:
            f.write(content)
        print(f"Saved patch to: {patch_path}")

        send_patch_received()

        if on_patch_received:
            on_patch_received(patch_path)
    except Exception as e:
        print(f"Error saving patch file: {e}")
        send_patch_applied(False, f"Failed to receive patch file: {str(e)}")


def client_handle_patch_library_file(
    message: dict,
    patch_dir: str,
    on_saved: Optional[Callable[[str, dict], None]] = None,
) -> None:
    """Save a patch file from the server library without applying it."""
    filename = message.get('filename', 'server_patch.json')
    content = message.get('content', b'')

    print(f"Received library patch file: {filename} ({len(content)} bytes)")

    os.makedirs(patch_dir, exist_ok=True)
    patch_path = os.path.join(patch_dir, filename)

    try:
        with open(patch_path, 'wb') as f:
            f.write(content)
        print(f"Saved library patch to: {patch_path}")

        if on_saved:
            on_saved(patch_path, message)
    except Exception as e:
        print(f"Error saving library patch file: {e}")


def client_handle_backup_download_chunk(
    message: dict,
    backup_transfers: Dict[str, dict],
    on_complete: Optional[Callable[[str, bool, Optional[str]], None]] = None,
) -> None:
    """Handle incoming backup archive chunks and extract when complete."""
    backup_name = message.get('backup_name')
    chunk_num = message.get('chunk_num')
    total_chunks = message.get('total_chunks')
    chunk_data = message.get('data')

    if not all([backup_name, isinstance(chunk_num, int), isinstance(total_chunks, int), chunk_data]):
        print(f"[error] BACKUP DOWNLOAD: Invalid chunk data")
        return

    if backup_name not in backup_transfers:
        backup_transfers[backup_name] = {
            'chunks': {},
            'total_chunks': total_chunks,
            'received_chunks': 0,
            'start_time': time.time()
        }

    transfer = backup_transfers[backup_name]

    if chunk_num not in transfer['chunks']:
        transfer['chunks'][chunk_num] = chunk_data
        transfer['received_chunks'] += 1

    if transfer['received_chunks'] == total_chunks:
        _client_assemble_backup_archive(backup_transfers, backup_name, on_complete)


def _client_assemble_backup_archive(
    backup_transfers: Dict[str, dict],
    backup_name: str,
    on_complete: Optional[Callable[[str, bool, Optional[str]], None]] = None,
) -> None:
    transfer = backup_transfers[backup_name]

    try:
        backup_data = b''
        for i in range(transfer['total_chunks']):
            if i not in transfer['chunks']:
                raise ValueError(f"Missing chunk {i} for backup {backup_name}")
            backup_data += transfer['chunks'][i]

        backup_dir = "__game_backups"
        os.makedirs(backup_dir, exist_ok=True)

        print(f"BACKUP DOWNLOAD: Extracting '{backup_name}' to {backup_dir}/")
        with io.BytesIO(backup_data) as bio:
            with tarfile.open(fileobj=bio, mode='r:gz') as tar:
                tar.extractall(path=backup_dir)

        extracted_backup_path = os.path.join(backup_dir, backup_name)
        if os.path.exists(extracted_backup_path):
            backup_handler = BackupHandler()
            computed_hash = backup_handler.compute_directory_hash(extracted_backup_path, debug=True)
            if computed_hash != backup_name:
                import shutil
                if os.path.isdir(extracted_backup_path):
                    shutil.rmtree(extracted_backup_path)
                elif os.path.isfile(extracted_backup_path):
                    os.remove(extracted_backup_path)
                raise ValueError(f"Hash verification failed: expected {backup_name}, got {computed_hash}")

        if on_complete:
            on_complete(backup_name, True, None)

    except Exception as e:
        print(f"[error] BACKUP DOWNLOAD: Failed to assemble backup {backup_name}: {e}")
        if on_complete:
            on_complete(backup_name, False, str(e))

    finally:
        if backup_name in backup_transfers:
            del backup_transfers[backup_name]


# ---------------------------
# Server-side helpers
# ---------------------------

def server_request_backup_from_client(server, player_id: str, backup_name: str) -> None:
    message = {
        'type': 'request_backup',
        'backup_name': backup_name
    }
    server._send_message_to_client(player_id, message)
    print(f"BACKUP REQUEST: Server sent backup request to client '{player_id}' for backup '{backup_name}'")


def server_send_patch_file(server, player_id: str, patch_file_path: str) -> None:
    try:
        def message_factory(chunk_num: int, total_chunks: int, chunk_data: bytes) -> dict:
            return {
                'type': 'patch_file_chunk',
                'filename': 'merge_patch.json',
                'chunk_num': chunk_num,
                'total_chunks': total_chunks,
                'data': chunk_data
            }

        outgoing_queue = []
        file_size = os.path.getsize(patch_file_path)
        # Use smaller chunk size (8KB) to prevent timeouts on large patches
        total_chunks = queue_chunked_file(outgoing_queue, patch_file_path, message_factory, chunk_size=8192)

        print(f"Sending merge patch to {player_id} ({total_chunks} chunks, {file_size} bytes)")
        
        for msg in outgoing_queue:
            server._send_message_to_client(player_id, msg)
            
    except Exception as e:
        print(f"Failed to send patch to {player_id}: {e}")


def client_handle_patch_file_chunk(
    message: dict,
    patch_transfers: Dict[str, dict],
    patch_dir: str,
    send_patch_received: Callable[[], None],
    send_patch_applied: Callable[[bool, Optional[str]], None],
    on_patch_received: Optional[Callable[[str], None]] = None,
) -> None:
    """Handle incoming patch file chunk from server."""
    filename = message.get('filename', 'merge_patch.json')
    chunk_num = message.get('chunk_num')
    total_chunks = message.get('total_chunks')
    chunk_data = message.get('data')

    if not all([isinstance(chunk_num, int), isinstance(total_chunks, int), chunk_data]):
        print(f"Invalid patch chunk received for {filename}")
        return

    if filename not in patch_transfers:
        patch_transfers[filename] = {
            'chunks': {},
            'total_chunks': total_chunks,
            'received_chunks': 0,
            'start_time': time.time()
        }

    transfer = patch_transfers[filename]

    if chunk_num not in transfer['chunks']:
        transfer['chunks'][chunk_num] = chunk_data
        transfer['received_chunks'] += 1
        
        # Optional: Print progress for large patches
        if total_chunks > 5 and transfer['received_chunks'] % 5 == 0:
             print(f"Patch download progress: {transfer['received_chunks']}/{total_chunks}")

    if transfer['received_chunks'] == total_chunks:
        try:
            # Assemble file
            os.makedirs(patch_dir, exist_ok=True)
            patch_path = os.path.join(patch_dir, filename)
            
            with open(patch_path, 'wb') as f:
                for i in range(total_chunks):
                    if i in transfer['chunks']:
                        f.write(transfer['chunks'][i])
                    else:
                        raise ValueError(f"Missing chunk {i}")
            
            print(f"Received and assembled patch file: {patch_path}")
            
            # Trigger success callbacks
            send_patch_received()

            if on_patch_received:
                on_patch_received(patch_path)
                
        except Exception as e:
            print(f"Error assembling patch file: {e}")
            send_patch_applied(False, f"Failed to assemble patch file: {str(e)}")
        finally:
            del patch_transfers[filename]



def server_send_file_chunks(server, player_id: str, file_path: str, full_path: str, chunk_size: int = 64 * 1024) -> None:
    """Send a file to a client in chunks."""
    try:
        file_size = os.path.getsize(full_path)
        total_chunks = (file_size + chunk_size - 1) // chunk_size

        with open(full_path, 'rb') as f:
            for chunk_num in range(total_chunks):
                chunk_data = f.read(chunk_size)

                chunk_message = {
                    'type': 'file_chunk',
                    'file_path': file_path,
                    'chunk_num': chunk_num,
                    'total_chunks': total_chunks,
                    'data': chunk_data
                }

                server._send_message_to_client(player_id, chunk_message)

        print(f"Sent file {file_path} to {player_id} ({total_chunks} chunks)")

    except Exception as e:
        print(f"Failed to send file {file_path} to {player_id}: {e}")
        response = {
            'type': 'file_complete',
            'file_path': file_path,
            'success': False,
            'error': str(e)
        }
        server._send_message_to_client(player_id, response)


def server_send_backup_archive(server, player_id: str, backup_name: str, chunk_size: int = 64 * 1024) -> bool:
    """Send a backup archive to a client in chunks. Returns True if started."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    backup_dir = os.path.join(project_root, "__game_backups")
    backup_path = os.path.join(backup_dir, backup_name)
    if not os.path.exists(backup_path):
        error_message = {
            'type': 'backup_download_failed',
            'backup_name': backup_name,
            'error': f"Backup '{backup_name}' not found on server"
        }
        server._send_message_to_client(player_id, error_message)
        return False

    temp_path = _create_backup_archive(backup_path)
    try:
        file_size = os.path.getsize(temp_path)
        total_chunks = (file_size + chunk_size - 1) // chunk_size

        with open(temp_path, 'rb') as f:
            for chunk_num in range(total_chunks):
                chunk_data = f.read(chunk_size)
                chunk_message = {
                    'type': 'backup_chunk',
                    'backup_name': backup_name,
                    'chunk_num': chunk_num,
                    'total_chunks': total_chunks,
                    'data': chunk_data
                }
                server._send_message_to_client(player_id, chunk_message)

        print(f"Sent backup archive {backup_name} to {player_id} ({total_chunks} chunks)")
        return True
    except Exception as e:
        error_message = {
            'type': 'backup_download_failed',
            'backup_name': backup_name,
            'error': str(e)
        }
        server._send_message_to_client(player_id, error_message)
        return False
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass


def server_handle_patch_chunk(server, player_id: str, message: dict) -> None:
    patch_name = message.get('patch_name')
    chunk_num = message.get('chunk_num')
    total_chunks = message.get('total_chunks')
    chunk_data = message.get('data')

    if not all([patch_name, isinstance(chunk_num, int), isinstance(total_chunks, int), chunk_data]):
        print(f"Invalid patch chunk from {player_id}")
        return

    key = f"{player_id}:{patch_name}"

    if key not in server.client_patch_files:
        server.client_patch_files[key] = {
            'chunks': {},
            'total': total_chunks,
            'received': 0
        }

    transfer = server.client_patch_files[key]

    if chunk_num not in transfer['chunks']:
        transfer['chunks'][chunk_num] = chunk_data
        transfer['received'] += 1

    if transfer['received'] == total_chunks:
        server_assemble_patch_file(server, player_id, patch_name)


def server_assemble_patch_file(server, player_id: str, patch_name: str) -> None:
    key = f"{player_id}:{patch_name}"
    transfer = server.client_patch_files[key]

    try:
        player_patch_dir = os.path.join(server.server_patches_dir, player_id)
        os.makedirs(player_patch_dir, mode=0o755, exist_ok=True)

        patch_path = os.path.join(player_patch_dir, f"{patch_name}.json")
        with open(patch_path, 'wb') as f:
            for chunk_num in range(transfer['total']):
                if chunk_num in transfer['chunks']:
                    f.write(transfer['chunks'][chunk_num])
                else:
                    raise ValueError(f"Missing chunk {chunk_num}")

        print(f"[success] Received complete patch from {player_id}: {patch_name}")

        # Add to database and delete file to save space
        if hasattr(server, 'patch_db'):
            try:
                with open(patch_path, 'r', encoding='utf-8') as f:
                    patch_data = json.load(f)
                
                # Calculate patch content hash for deduplication
                changes_str = json.dumps(patch_data.get("changes", []), sort_keys=True)
                patch_hash = hashlib.sha256(changes_str.encode('utf-8')).hexdigest()
                
                patch_db_id = server.patch_db.add_patch(patch_data, player_id, patch_hash, name=patch_name)
                print(f"    ✓ Stored in DB (ID: {patch_db_id})")
                
                # We can delete the file now, as we'll recreate it when needed for merging
                os.remove(patch_path)
                print(f"    ✓ Deleted temporary patch file: {patch_path}")
            except Exception as db_err:
                print(f"    [error] Failed to store patch in DB: {db_err}")

        del server.client_patch_files[key]

    except Exception as e:
        print(f"Failed to assemble patch from {player_id}: {e}")


def server_handle_file_chunk(server, player_id: str, message: dict) -> None:
    chunk_num = message.get('chunk_num')
    total_chunks = message.get('total_chunks')
    chunk_data = message.get('data')
    is_backup = message.get('is_backup', False)

    if is_backup:
        server_handle_backup_chunk(server, player_id, message)
        return
    file_path = message.get('file_path')

    if not all([file_path, isinstance(chunk_num, int), isinstance(total_chunks, int), chunk_data]):
        print(f"Invalid file chunk from {player_id}")
        return

    if not hasattr(server, 'client_file_transfers'):
        server.client_file_transfers = {}

    client_key = f"{player_id}:{file_path}"
    if client_key not in server.client_file_transfers:
        server.client_file_transfers[client_key] = {
            'chunks': {},
            'total_chunks': total_chunks,
            'received_chunks': 0
        }

    transfer = server.client_file_transfers[client_key]

    if chunk_num not in transfer['chunks']:
        transfer['chunks'][chunk_num] = chunk_data
        transfer['received_chunks'] += 1

    if transfer['received_chunks'] == total_chunks:
        server_assemble_client_file(server, player_id, file_path)


def server_assemble_client_file(server, player_id: str, file_path: str) -> None:
    client_key = f"{player_id}:{file_path}"
    transfer = server.client_file_transfers[client_key]

    try:
        allowed_dirs = ['uploads', 'temp']
        target_dir = allowed_dirs[0] if 'uploads' in allowed_dirs else 'temp'

        project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        full_dir = os.path.join(project_root, target_dir)
        os.makedirs(full_dir, exist_ok=True)

        safe_filename = os.path.basename(file_path).replace('..', '').replace('/', '_').replace('\\', '_')
        full_path = os.path.join(full_dir, f"{player_id}_{safe_filename}")

        with open(full_path, 'wb') as f:
            for chunk_num in range(transfer['total_chunks']):
                if chunk_num in transfer['chunks']:
                    f.write(transfer['chunks'][chunk_num])
                else:
                    raise ValueError(f"Missing chunk {chunk_num}")

        response = {
            'type': 'file_complete',
            'file_path': file_path,
            'success': True,
            'saved_path': full_path
        }
        server._send_message_to_client(player_id, response)

        print(f"Received and saved file from {player_id}: {full_path}")

    except Exception as e:
        print(f"Failed to assemble file from {player_id}: {e}")
        response = {
            'type': 'file_complete',
            'file_path': file_path,
            'success': False,
            'error': str(e)
        }
        server._send_message_to_client(player_id, response)

    finally:
        if client_key in server.client_file_transfers:
            del server.client_file_transfers[client_key]


def server_handle_backup_chunk(server, player_id: str, message: dict) -> None:
    backup_name = message.get('backup_name')
    chunk_num = message.get('chunk_num')
    total_chunks = message.get('total_chunks')
    chunk_data = message.get('data')

    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{timestamp}] BACKUP CHUNK: Received chunk {chunk_num+1 if isinstance(chunk_num, int) else '?'} from {player_id} for '{backup_name}'")
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{timestamp}] DEBUG: Message details - backup: {backup_name}, chunk: {chunk_num}/{total_chunks}, data_size: {len(chunk_data) if chunk_data else 0} bytes")
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{timestamp}] DEBUG: Current transfer state - in_progress: {getattr(server, 'backup_transfer_in_progress', False)}, expected_backup: {getattr(server, 'backup_transfer_name', 'None')}")

    if not all([backup_name, isinstance(chunk_num, int), isinstance(total_chunks, int), chunk_data]):
        print(f"[error] BACKUP CHUNK: Invalid backup chunk from {player_id}: missing or invalid fields")
        return

    if total_chunks <= 0:
        print(f"[error] BACKUP CHUNK: Invalid total_chunks {total_chunks} from {player_id}")
        return

    if chunk_num < 0 or chunk_num >= total_chunks:
        print(f"[error] BACKUP CHUNK: Invalid chunk_num {chunk_num} (should be 0-{total_chunks-1}) from {player_id}")
        return

    if not hasattr(server, 'client_backup_transfers'):
        server.client_backup_transfers = {}

    client_key = f"{player_id}:{backup_name}"
    if client_key not in server.client_backup_transfers:
        print(f"BACKUP CHUNK: Starting new transfer for '{backup_name}' from {player_id} ({total_chunks} chunks total)")
        server.client_backup_transfers[client_key] = {
            'chunks': {},
            'total_chunks': total_chunks,
            'received_chunks': 0,
            'start_time': time.time()
        }

    transfer = server.client_backup_transfers[client_key]

    if chunk_num not in transfer['chunks']:
        transfer['chunks'][chunk_num] = chunk_data
        transfer['received_chunks'] += 1
        progress = transfer['received_chunks'] / total_chunks * 100
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"[{timestamp}] [success] BACKUP CHUNK: Stored chunk {chunk_num+1}/{total_chunks} ({progress:.1f}%) for '{backup_name}' from {player_id}")
        print(f"[{timestamp}] DEBUG: Chunk received - backup: {backup_name}, received: {transfer['received_chunks']}/{total_chunks}")
    else:
        print(f"[warning] BACKUP CHUNK: Duplicate chunk {chunk_num} for '{backup_name}' from {player_id}")

    if transfer['received_chunks'] == total_chunks:
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"[{timestamp}] BACKUP CHUNK: All {total_chunks} chunks received for '{backup_name}' from {player_id}, starting assembly...")
        print(f"[{timestamp}] DEBUG: Starting backup assembly for {backup_name}")
        success = server_assemble_client_backup(server, player_id, backup_name)

        if success:
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"[{timestamp}] [success] DEBUG: Backup assembly successful for {backup_name}")
            if getattr(server, 'backup_transfer_in_progress', False):
                if backup_name == getattr(server, 'backup_transfer_name', None):
                    print(f"[{timestamp}] BACKUP TRANSFER: Successfully completed transfer of '{backup_name}'")
                    print(f"[{timestamp}] DEBUG: Setting backup_transfer_complete_event for {backup_name}")
                    server.backup_transfer_in_progress = False
                    if hasattr(server, 'backup_transfer_complete_event'):
                        server.backup_transfer_complete_event.set()
                        print(f"[{timestamp}] DEBUG: backup_transfer_complete_event.set() called")
                    else:
                        print(f"[{timestamp}] [warning] DEBUG: backup_transfer_complete_event not found!")
        else:
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"[{timestamp}] BACKUP TRANSFER: Assembly failed for '{backup_name}' from {player_id}")
            if hasattr(server, 'backup_transfer_complete_event'):
                server.backup_transfer_complete_event.set()
                print(f"[{timestamp}] DEBUG: backup_transfer_complete_event.set() called (failure)")
            else:
                print(f"[{timestamp}] [warning] DEBUG: backup_transfer_complete_event not found on failure!")


def server_assemble_client_backup(server, player_id: str, backup_name: str) -> bool:
    client_key = f"{player_id}:{backup_name}"
    if client_key not in server.client_backup_transfers:
        print(f"[error] BACKUP ASSEMBLY: No transfer data found for '{backup_name}' from {player_id}")
        return False

    transfer = server.client_backup_transfers[client_key]
    print(f"BACKUP ASSEMBLY: Starting assembly of '{backup_name}' from {player_id} ({transfer['total_chunks']} chunks)")

    try:
        backup_data = b''
        for i in range(transfer['total_chunks']):
            if i not in transfer['chunks']:
                print(f"[error] BACKUP ASSEMBLY: Missing chunk {i} for backup {backup_name}")
                return False
            backup_data += transfer['chunks'][i]

        print(f"BACKUP ASSEMBLY: Assembled {len(backup_data)} bytes of compressed data for '{backup_name}'")

        backup_dir = "__game_backups"
        os.makedirs(backup_dir, exist_ok=True)

        print(f"BACKUP ASSEMBLY: Extracting '{backup_name}' to {backup_dir}/")
        with io.BytesIO(backup_data) as bio:
            with tarfile.open(fileobj=bio, mode='r:gz') as tar:
                tar.extractall(path=backup_dir)

        print(f"[success] BACKUP ASSEMBLY: Successfully extracted backup '{backup_name}' from {player_id}")

        extracted_backup_path = os.path.join(backup_dir, backup_name)
        if os.path.exists(extracted_backup_path):
            backup_handler = BackupHandler()
            computed_hash = backup_handler.compute_directory_hash(extracted_backup_path, debug=True)
            if computed_hash != backup_name:
                print(f"[error] BACKUP ASSEMBLY: Hash verification FAILED for '{backup_name}' from {player_id}")
                print(f"   Expected hash: {backup_name}")

                if os.path.isdir(extracted_backup_path):
                    import shutil
                    shutil.rmtree(extracted_backup_path)
                elif os.path.isfile(extracted_backup_path):
                    os.remove(extracted_backup_path)

                error_message = {
                    'type': 'backup_transfer_failed',
                    'backup_name': backup_name,
                    'error': f'Hash verification failed: expected {backup_name}, got {computed_hash}'
                }
                server._send_message_to_client(player_id, error_message)
                print(f"BACKUP ASSEMBLY: Sent hash verification failure acknowledgment to {player_id}")
                return False

            print(f"[success] BACKUP ASSEMBLY: Hash verification PASSED for '{backup_name}' from {player_id}")

        del server.client_backup_transfers[client_key]

        ack_message = {
            'type': 'backup_transfer_success',
            'backup_name': backup_name
        }
        server._send_message_to_client(player_id, ack_message)
        print(f"BACKUP ASSEMBLY: Sent success acknowledgment to {player_id} for '{backup_name}'")

        return True

    except Exception as e:
        print(f"[error] BACKUP ASSEMBLY: Failed to assemble backup {backup_name} from {player_id}: {e}")

        error_message = {
            'type': 'backup_transfer_failed',
            'backup_name': backup_name,
            'error': str(e)
        }
        server._send_message_to_client(player_id, error_message)
        print(f"BACKUP ASSEMBLY: Sent failure acknowledgment to {player_id} for '{backup_name}': {e}")

        return False
