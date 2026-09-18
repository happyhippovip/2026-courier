# CODEX REVIEW PACKET — DLQ-06 Windows Ledger Race Condition

CURRENT_HEAD=1b492d0a0496cb81d1a70565c6098c7817597645
COMMITS_UNDER_REVIEW=
- 1b492d0a test: deterministic behavioral reproducer for DLQ-06 Windows ledger race

INVARIANTS=
1. Concurrent readers must not crash writers. `atomic_write` must safely retry replacing the file if a reader holds it open.
2. Concurrent writers must not crash readers. `load_bundle` must safely retry reading the file if a writer holds it open.
3. Persistent errors must fail boundedly, preventing infinite hangs.

DIFF_SCOPE=tests/test_windows_ledger_race.py: Replaced the static AST check with dynamic monkeypatching of `Path.read_text` and `os.replace` to simulate transient Windows `PermissionError`s. The tests now verify target behavioral requirements by asserting the operations succeed if contention clears, and fail cleanly boundedly on persistent errors.

EXACT_FILES=tests/test_windows_ledger_race.py
EXACT_FUNCTIONS=load_bundle(), atomic_write()

REPRODUCERS=
- DLQ-06: python3 -m pytest tests/test_windows_ledger_race.py (The read and write transient tests currently FAIL, proving the defect is present in the unpatched `agent_handoff_ledger.py`.)

EXPECTED_FAIL_CURRENT=YES, transient tests fail because `agent_handoff_ledger.py` lacks a retry loop.

BOUNDED_RETRY_DESIGN=
- EXACT_EXCEPTION: `PermissionError` ONLY.
- RETRY_BOUNDARY: Wrap `path.read_text` in `load_bundle`, and `os.replace` in `atomic_write`.
- MAX_ATTEMPT_RECOMMENDATION: 20 max attempts (matching `server/app.py` `load_state()`), equating to ~1 second deadline.
- BACKOFF_RECOMMENDATION: Fixed 0.05s delay (or slightly jittered).
- UNSAFE_BROAD_RETRY: Broadly retrying `OSError` or `json.JSONDecodeError` would be unsafe. If a file is permanently corrupted by a manual edit or hardware issue, infinite or broad retry would mask the corruption and hang the Motor loop. Strict `PermissionError` bounding isolates the retry specifically to OS-level file locking semantics.

WINDOWS_PHYSICAL_STILL_REQUIRED=YES. The mock validates the logic, but the actual file-locking characteristics must be physically proven on a Windows worker.

CODEX_READY=YES 
