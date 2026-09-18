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

## MUSE COMPLETION ADDENDUM (2026-09-18, HEAD 5a8befb7 — corrections, body preserved)

HEAD_CORRECTION: CURRENT_HEAD above names 1b492d0a (chore); the reviewed test
commit is 5a8befb7b19a436a8ded2dd619c7ea32645023c2. COMMITS_UNDER_REVIEW
corrected to: 5a8befb7 (behavioral tests) + ceba1fe0 (motor context, no ledger
content) + 1b492d0a (chore/metadata).
T2_RESULTS (Muse, HEAD 5a8befb7): tests/test_windows_ledger_race.py → 2 FAILED
(read_transient, write_transient) + 1 PASSED (persistent_failure). The red
suite is DECLARED (EXPECTED_FAIL_CURRENT=YES): tests assert post-fix behavior
on unfixed code. Suite stays red until Google lands the PermissionError-only
retry; tests must NOT be weakened, production fix is Google-owned.
T3_RESULTS (Muse, HEAD 5a8befb7): ledger false-green + edge-conservation +
duplicate-contract + fix-guards = 11 passed; node truth pass 1 fail 0.
Ledger area unaffected by this tests-only batch.
KNOWN_ATTACKS: masking corruption via broad OSError/JSON retry (design
excludes it — PermissionError-only); infinite hang via unbounded retry
(design bounds at ~20 attempts); pre-fix Windows crash (live, parked for
Google + Windows worker).
FILES_TO_READ (bounded): tests/test_windows_ledger_race.py (whole file, ~90
lines); scripts/agent_handoff_ledger.py load_bundle/atomic_write (retry
insertion points); server/app.py load_state() (retry-shape reference).
QUESTIONS_TO_ANSWER: 1. Confirm 20-attempt/0.05s shape vs Windows lock-hold
durations observed physically. 2. Reader-side AND writer-side retry land in
one commit with the tripwire flip? 3. Who runs the 50-cycle Windows collision
(worker commands: ops/ai/packets/WINDOWS_DLQ06-worker-commands.md)?
CODEX_READY_CONFIRMED=YES (with this addendum; red T2 explicitly parked as
awaiting-implementation, not as packet defect).
