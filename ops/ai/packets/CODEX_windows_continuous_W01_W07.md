# Codex Handoff Packet: Windows Continuous Work (W01 - W07)

CURRENT_HEAD=fc1f42dda22f034b12944ac6da6d338712100a1b
COMMITS_UNDER_REVIEW=
3039126e - W02: Fix DLQ-06 transient Windows PermissionError on load/write (agent_handoff_ledger.py)
bbc86b56 - W03/W04/W05/W06: Fix Motor hang/exception swallow, server infinite retry, silent unblock (courier_continue.py, server/app.py)
8918bc8f - W07: Reject CANONICAL_ACCEPTED and VALID MACHINE_ARTIFACT plants in initialize() (agent_handoff_ledger.py)
fc1f42dd - Fix test suite REDACTED auth header in provider wait tests.

INVARIANTS:
1. W02: Transient PermissionError -> bounded retry -> eventual success. Persistent -> bounded error.
2. W03: One hung future must not wedge the Motor. Bounded drain implemented (8s).
3. W04: Crashed Motor task truthfully records EXCEPTION blocker, doesn't swallow.
4. W05: Server MAX_RETRIES execution/verification loops terminate in FAILED_TERMINAL, never loop infinitely.
5. W06: Successful branch cannot overwrite an unrelated concurrent BLOCKED state with READY.
6. W07: INIT is NEVER CANONICAL_ACCEPTED and cannot plant validated MACHINE_ARTIFACT.

DIFF_SCOPE:
scripts/agent_handoff_ledger.py
scripts/courier_continue.py
server/app.py

REPRODUCERS:
- test_windows_ledger_race.py (W02)
- /tmp/motor_hang_bound.py (W03)
- G5 AST test proofs (W04, W05, W06)

T2_RESULTS: PASS
T3_RESULTS: PASS

KNOWN_ATTACKS:
- W07: Planted MACHINE_ARTIFACT on INIT is stripped and marked INVALID.
- W06: Concurrency race on update_ledger preserves FIRST_CAUSAL_BLOCKER.

FILES_TO_READ:
ops/ai/WINDOWS_CONTINUOUS_WORK.yaml
scripts/agent_handoff_ledger.py
scripts/courier_continue.py
server/app.py

QUESTIONS_TO_ANSWER:
None.
