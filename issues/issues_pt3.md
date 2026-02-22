# Audit Findings (Part 3)

## Finding 19
- File path: `launcher/proxy_tools/__init__.py`
- Issue type: Python 2 compatibility symbols exposed in Python 3 code paths
- Severity: High
- Explanation: Python 2-only operations (`cmp`, `long`, `__div__`, `__coerce__`, `__rdiv__`) were defined on the proxy class for Python 3 runtimes.
- Why it is a problem: Using those operators in Python 3 can raise `NameError`/attribute errors and break launcher runtime behavior unexpectedly.
- Concrete proposed fix: Guard Python 2-only operator implementations behind `if PY2:` and provide Python 3-safe division behavior.
- Optional refactor suggestion: Replace this legacy proxy module with a maintained Python 3 native proxy implementation.

## Finding 20
- File path: `pytest.ini` (new)
- Issue type: Test architecture inconsistency / non-deterministic collection
- Severity: Medium
- Explanation: Running `pytest` from repo root originally collected backup snapshots under `__game_backups` and produced duplicate-module import mismatches.
- Why it is a problem: CI/local test runs become flaky or fail before executing the real suite.
- Concrete proposed fix: Add deterministic pytest configuration (`pythonpath = .`, `testpaths = GameFolder/tests`, and `norecursedirs` for generated directories).
- Optional refactor suggestion: Split fast unit tests and slower integration/E2E tests into explicit pytest markers.

## High/Critical Remediation Status
- `server.py` insecure deserialization + message-size hardening: Addressed.
- `BASE_files/network_client.py` insecure deserialization + message-size hardening: Addressed.
- `BASE_files/transfer_manager.py` path traversal and unsafe archive extraction: Addressed.
- `BASE_files/BASE_menu.py` unsafe async thread-kill behavior: Addressed via cooperative stop request flow.
- `.env` workspace secret exposure: Addressed by redaction in workspace (keys still must be rotated externally).

## Finding 21
- File path: `agent.py`
- Issue type: Logic bug in deferred conflict-resolution flow
- Severity: High
- Explanation: The code imported `_defer_application` as a local name and reassigned it, which does not mutate the original module-level flag used by conflict resolution.
- Why it is a problem: Deferred resolution mode may not activate correctly, causing incorrect conflict application order and unstable merge behavior.
- Concrete proposed fix: Mutate the module attribute directly (`import coding.tools.conflict_resolution as conflict_resolution` then set `conflict_resolution._defer_application`).
- Optional refactor suggestion: Replace mutable module globals with an explicit context object passed to resolver APIs.
