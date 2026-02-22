import io
import json
import os
import pickle
import tarfile
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from BASE_files.safe_serialization import safe_pickle_loads
from BASE_files import transfer_manager


class _ExploitPayload:
    def __reduce__(self):
        return (os.system, ("echo exploit",))


class _DummyServer:
    def __init__(self, patches_dir: Path):
        self.client_patch_files = {}
        self.server_patches_dir = str(patches_dir)

    def _send_message_to_client(self, _player_id, _message):
        # Not needed for these tests.
        return None


def test_safe_pickle_rejects_unsafe_globals():
    payload = pickle.dumps(_ExploitPayload(), protocol=4)
    with pytest.raises(pickle.UnpicklingError):
        safe_pickle_loads(payload)


def test_safe_pickle_accepts_primitive_messages():
    message = {
        "type": "input",
        "input_id": 42,
        "movement": [1, 0],
        "flags": {"dash": True},
        "blob": b"abc",
    }
    decoded = safe_pickle_loads(pickle.dumps(message, protocol=4))
    assert decoded == message


def test_client_file_chunk_blocks_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(transfer_manager, "_project_root", lambda: str(tmp_path))
    file_transfers = {}
    outgoing_queue = []

    message = {
        "file_path": "../../outside.txt",
        "chunk_num": 0,
        "total_chunks": 1,
        "data": b"bad-data",
    }

    transfer_manager.client_handle_file_chunk(
        message,
        file_transfers,
        outgoing_queue,
        player_id="player1",
    )

    assert outgoing_queue
    assert outgoing_queue[-1]["type"] == "file_ack"
    assert outgoing_queue[-1]["success"] is False
    assert not (tmp_path / "outside.txt").exists()


def test_client_file_chunk_writes_only_whitelisted_targets(tmp_path, monkeypatch):
    monkeypatch.setattr(transfer_manager, "_project_root", lambda: str(tmp_path))
    file_transfers = {}
    outgoing_queue = []
    target_path = "GameFolder/security/test.txt"

    message = {
        "file_path": target_path,
        "chunk_num": 0,
        "total_chunks": 1,
        "data": b"safe-data",
    }

    transfer_manager.client_handle_file_chunk(
        message,
        file_transfers,
        outgoing_queue,
        player_id="player1",
    )

    saved = tmp_path / target_path
    assert saved.exists()
    assert saved.read_bytes() == b"safe-data"
    assert outgoing_queue[-1]["success"] is True


def test_server_patch_chunk_rejects_traversal_name(tmp_path):
    server = _DummyServer(tmp_path / "server_patches")
    message = {
        "patch_name": "../../evil",
        "chunk_num": 0,
        "total_chunks": 1,
        "data": b'{"changes": []}',
    }

    transfer_manager.server_handle_patch_chunk(server, "player1", message)
    assert server.client_patch_files == {}
    assert not (tmp_path / "evil.json").exists()


def test_server_patch_chunk_sanitizes_and_saves_valid_patch(tmp_path):
    server = _DummyServer(tmp_path / "server_patches")
    payload = {"name_of_backup": "base", "prompt_used": "x", "changes": []}
    message = {
        "patch_name": "my patch",
        "chunk_num": 0,
        "total_chunks": 1,
        "data": json.dumps(payload).encode("utf-8"),
    }

    transfer_manager.server_handle_patch_chunk(server, "player1", message)
    patch_path = tmp_path / "server_patches" / "player1" / "my_patch.json"
    assert patch_path.exists()


def test_safe_extract_tar_stream_rejects_traversal_member(tmp_path):
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as tar:
        bad_data = b"owned"
        bad_info = tarfile.TarInfo(name="../evil.txt")
        bad_info.size = len(bad_data)
        tar.addfile(bad_info, io.BytesIO(bad_data))

    archive.seek(0)
    with pytest.raises(ValueError):
        transfer_manager._safe_extract_tar_stream(archive, str(tmp_path))


def test_create_file_supports_repo_root_relative_paths(tmp_path, monkeypatch):
    from coding.tools import file_handling

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(file_handling, "is_file_allowed", lambda path, operation="write": True)
    monkeypatch.setattr(file_handling.action_logger, "snapshot_file", lambda path: None)
    monkeypatch.setattr(file_handling.action_logger, "record_file_change", lambda path: None)

    result = file_handling.create_file(path="root_level.txt")
    assert (tmp_path / "root_level.txt").exists()
    assert "Successfully created empty file" in result
