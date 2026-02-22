# Audit Findings (Part 2)

## Finding 2
- File path: `server.py`
- Issue type: Insecure deserialization over network (`pickle.loads` on socket input)
- Severity: Critical
- Explanation: The server deserializes untrusted client data using `pickle.loads`.
- Why it is a problem: Pickle supports object opcodes that can execute arbitrary code during load, enabling remote code execution from a malicious client.
- Concrete proposed fix: Replace raw pickle deserialization with a restricted unpickler that blocks globals/classes, enforce strict message schema validation, and move protocol toward msgpack/json for control messages.
- Optional refactor suggestion: Centralize wire serialization/deserialization in a dedicated safe serialization module used by both client and server.

## Finding 3
- File path: `BASE_files/network_client.py`
- Issue type: Insecure deserialization over network (`pickle.loads` on socket input)
- Severity: Critical
- Explanation: The client deserializes server messages and game-state payloads with raw `pickle.loads`.
- Why it is a problem: A malicious or compromised server can trigger code execution in clients.
- Concrete proposed fix: Use the same restricted unpickler and schema checks as server-side; reject unsafe payloads.
- Optional refactor suggestion: Version the protocol and route control/game-state serialization through one compatibility layer.

## Finding 4
- File path: `server.py`
- Issue type: Missing input bounds / protocol hardening
- Severity: High
- Explanation: Length-prefixed socket messages are accepted without a strict maximum message size check.
- Why it is a problem: A malicious client can advertise extremely large lengths and force memory/time exhaustion (DoS).
- Concrete proposed fix: Reject non-positive or oversized message lengths (e.g., >8MB) before reading message body and disconnect offending client.
- Optional refactor suggestion: Introduce configurable transport limits (max frame size, max chunk size, rate limits) in one constants module.

## Finding 5
- File path: `BASE_files/transfer_manager.py`
- Issue type: Path traversal (client file chunk assembly)
- Severity: Critical
- Explanation: `client_handle_file_chunk`/`_client_assemble_file` write server-provided `file_path` to disk without canonical safe-root enforcement.
- Why it is a problem: A malicious server can overwrite arbitrary local files via paths like `../../...`.
- Concrete proposed fix: Normalize and validate path against explicit allowed roots, reject absolute/parent traversal segments, and acknowledge failure to sender.
- Optional refactor suggestion: Add a shared path sanitizer used by all transfer entry points.

## Finding 6
- File path: `BASE_files/transfer_manager.py`
- Issue type: Path traversal (patch filenames from network)
- Severity: Critical
- Explanation: Patch file save handlers accept network-provided filenames with insufficient sanitization.
- Why it is a problem: Crafted names can escape target directory or overwrite unintended files.
- Concrete proposed fix: Sanitize to basename, enforce `.json` extension, and whitelist filename characters.
- Optional refactor suggestion: Route all inbound filenames through one `safe_filename(...)` utility.

## Finding 7
- File path: `BASE_files/transfer_manager.py`
- Issue type: Path traversal (server patch assembly from client-controlled patch name)
- Severity: High
- Explanation: `server_assemble_patch_file` builds `<player_dir>/<patch_name>.json` from untrusted `patch_name`.
- Why it is a problem: Unvalidated patch names can break directory boundaries and write arbitrary files.
- Concrete proposed fix: Sanitize patch names to safe token set (alnum/`_`/`-`), reject invalid names, and isolate per-player patch directories.
- Optional refactor suggestion: Include patch UUID server-side and avoid using user-controlled names in filesystem paths.

## Finding 8
- File path: `BASE_files/BASE_menu.py`
- Issue type: Unsafe thread termination
- Severity: High
- Explanation: `_kill_agent_thread` uses `PyThreadState_SetAsyncExc` to asynchronously raise `SystemExit` in another thread.
- Why it is a problem: Async thread interruption can leave locks/resources in inconsistent states and corrupt interpreter behavior.
- Concrete proposed fix: Replace hard-kill with cooperative cancellation (threading.Event) and safe shutdown checkpoints.
- Optional refactor suggestion: Move long-running agent execution to a separate process for stronger isolation and kill semantics.

## Finding 9
- File path: `.env`
- Issue type: Secret exposure / credential management
- Severity: Critical
- Explanation: Workspace `.env` contained hard-coded live-looking API keys.
- Why it is a problem: Credential leakage enables abuse, financial loss, and unauthorized access; exposure persists in any shared copies/history.
- Concrete proposed fix: Replace committed secrets with placeholders, immediately rotate/revoke exposed keys, and use secure runtime secret injection.
- Optional refactor suggestion: Add secret-scanning in CI and a committed `.env.example` template.

## Finding 10
- File path: `coding/tools/file_handling.py`
- Issue type: Root-path file creation bug
- Severity: Medium
- Explanation: `create_file` calls `os.makedirs(os.path.dirname(path), exist_ok=True)` even when `dirname == ''`.
- Why it is a problem: Creating files at repository root can fail with `FileNotFoundError`.
- Concrete proposed fix: Guard empty dirname before `os.makedirs` (`if dir_name: ...`).
- Optional refactor suggestion: Add input normalization and path validation tests for create/write helpers.

## Finding 11
- File path: `BASE_components/BASE_asset_handler.py`
- Issue type: Logic bug (asset prefix ignored during frame counting)
- Severity: Medium
- Explanation: `get_animation_from_category` accepts `asset_prefix` but frame counting ignores it.
- Why it is a problem: Prefixed animation sets report zero frames and incorrectly fall back.
- Concrete proposed fix: Pass `asset_prefix` into frame-counting logic and ensure cache key matches naming mode.
- Optional refactor suggestion: Consolidate animation path resolution in one helper to avoid split logic.

## Finding 12
- File path: `GameFolder/setup.py`
- Issue type: Spawn bounds inconsistency in fullscreen mode
- Severity: Medium
- Explanation: Arena can use fullscreen dimensions while spawn generator still uses default width/height args.
- Why it is a problem: Characters may spawn off-screen or in invalid positions when fullscreen size differs.
- Concrete proposed fix: Use effective arena dimensions for spawn generation/clamping.
- Optional refactor suggestion: Introduce one `arena_dimensions` source of truth passed to all spawn helpers.

## Finding 13
- File path: `GameFolder/characters/GAME_character.py`
- Issue type: State consistency bug on invalid passive ability
- Severity: Low
- Explanation: `passive_ability_name` is set before ability lookup is validated.
- Why it is a problem: UI/state can claim a passive is active when no passive effects were applied.
- Concrete proposed fix: Only set `passive_ability_name` after successful lookup; clear/reset on invalid name.
- Optional refactor suggestion: Return explicit status (`True/False`) from passive assignment and enforce in callers.

## Finding 14
- File path: `visual_logger/frontend/app.js`
- Issue type: Mixed-content websocket bug
- Severity: Medium
- Explanation: WebSocket URL is hardcoded to `ws://`.
- Why it is a problem: Dashboard breaks under HTTPS due to browser mixed-content blocking.
- Concrete proposed fix: Choose `ws://` vs `wss://` based on current page protocol.
- Optional refactor suggestion: Centralize socket connect/retry/auth URL generation.

## Finding 15
- File path: `visual_logger/server.py`
- Issue type: Missing authentication on remote-exposable logging endpoints
- Severity: Medium
- Explanation: WebSocket/REST endpoints have no auth while host binding can be non-local.
- Why it is a problem: Exposes logs/actions to unauthorized network users if bound externally.
- Concrete proposed fix: Require bearer/shared-token auth (or force localhost bind by default for insecure mode).
- Optional refactor suggestion: Add a reusable request guard/dependency for all endpoints.

## Finding 16
- File path: `visual_logger/test_visual.py`
- Issue type: Non-terminating test/demo script
- Severity: Medium
- Explanation: Script ends with infinite sleep loop.
- Why it is a problem: CI or scripted runs hang indefinitely.
- Concrete proposed fix: Add a finite keepalive duration or CLI flag for blocking behavior.
- Optional refactor suggestion: Split into `demo_run()` and `keep_alive()` entry modes.

## Finding 17
- File path: `visual_logger/frontend/styles.css`
- Issue type: Undefined CSS variable
- Severity: Low
- Explanation: `--bg-hover` is referenced without definition.
- Why it is a problem: Hover styling silently degrades.
- Concrete proposed fix: Define `--bg-hover` or provide fallback in `var(...)` use.
- Optional refactor suggestion: Add a style lint pass for undefined custom properties.

## Finding 18
- File path: `BASE_files/network_client.py` and `server.py`
- Issue type: Protocol framing robustness
- Severity: Medium
- Explanation: 4-byte message length header handling is not robust against short reads in non-blocking mode.
- Why it is a problem: Partial headers can desynchronize stream parsing and cause disconnect loops.
- Concrete proposed fix: Read fixed-length headers with an exact-read helper and only parse when all 4 bytes are present.
- Optional refactor suggestion: Add transport unit tests using partial/chunked socket reads.
