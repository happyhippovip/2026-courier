# CODEX REVIEW PACKET — motor batch DLQ-04 fix + DLQ-06 tripwire (COMPLETE)

CURRENT_HEAD=82bbe0908dfd7db55b5820974f1c0b11e570d7a1
COMMITS_UNDER_REVIEW=
- 17b39cbc fix(motor): drain loop timing flake and state staleness (DLQ-04)
- 753594e8 test: add T1 static test for DLQ-06 Windows ledger race
(82bbe090 is docs-only handoff prep; no runtime content.)

INVARIANTS=
1. --once exits only after futures settle OR bounded drain timeout, independent
   of iteration count.
2. A non-empty done_edges set forces loop continuation (finished tasks unblock
   dependents; frontier must be recomputed, not exited).
3. Concurrent ledger readers must not crash writers (DLQ-06, OPEN — tripwire
   test pins the defect, fix pending Google/Windows).

DIFF_SCOPE=scripts/courier_continue.py main(): two exit-condition lines
(approx :495 and :573) gain the conjunct
(`done_edges` not in locals() or not done_edges). No ledger, guard, or server
change. Queue metadata updated (DLQ-04 IMPLEMENTED_AND_VERIFIED, DLQ-06 filed).

EXACT_FILES=scripts/courier_continue.py, tests/test_windows_ledger_race.py,
ops/ai/DEFERRED_LEDGER_QUEUE.yaml (metadata only)
EXACT_FUNCTIONS=main() --once exit conditions (2 sites);
load_bundle() named as DLQ-06 defect site (NOT changed — read-only reference)

REPRODUCERS=
- DLQ-04: python3 -m pytest tests/test_courier_continue.py -q ( acceptance
  pair flaked under load via early UNKNOWN exit pre-fix).
- DLQ-06: python3 -m pytest tests/test_windows_ledger_race.py -q (static AST
  tripwire: passes WHILE defect present, must be flipped when fixed).

T0_RESULTS=py_compile scripts/courier_continue.py + tests/test_windows_ledger_race.py
OK (Muse, 2026-09-18, HEAD 82bbe090)
T1_RESULTS=tests/test_windows_ledger_race.py 1 passed (defect pinned present);
targeted DLQ-04 pair covered inside T2 file
T2_RESULTS=tests/test_courier_continue.py 15/15 passed in 31.25s, independently
re-run by Muse at HEAD 82bbe090 (handoff claimed 22.59s at 753594e8 — same
suite, machine-timing delta only)
T3_RESULTS=tests/test_ledger_false_green_attack.py +
tests/test_ledger_edge_conservation_regression.py 6 passed; node --test
tests/test_execution_truth.mjs pass 1 fail 0 (Muse, HEAD 82bbe090 — handoff's
waiver replaced with a real run)

KNOWN_ATTACKS=
- Fast Unverified Completion via forced once_dispatched (exit now additionally
  gated on done_edges drain — attack window narrowed, not formally proven shut).
- Windows concurrent-read PermissionError crash (DLQ-06, live tripwire).
- Stale-frontier dispatch after ledger update (fix recomputes frontier;
  starvation shape covered by invariant 2).

BYPASSES_ALREADY_TRIED=
- MOCK iters games (mock_iters inflation) — addressed by bounded-drain design.
- done_edges non-empty at exit check — now blocks exit (this diff).
- Direct ledger-preset acceptance (DLQ-01/02 family) — untouched by this diff,
  still open, separate packets ops/ai/packets/DLQ-01_review_packet.md and
  DLQ-02_review_packet.md.

FILES_TO_READ (bounded)=
- scripts/courier_continue.py:480-500, 560-580 (exit conditions)
- scripts/courier_continue.py:531-545 (retry split, context)
- tests/test_windows_ledger_race.py (34 lines, whole file)
- ops/ai/packets/DLQ-03_review_packet.md (duplicate-semantics contract this
  motor loop relies on)

QUESTIONS_TO_ANSWER=
1. Does the done_edges conjunct fully close the early-exit flake under all
   heavy-load interleavings, or is a monotonic drain-deadline still required?
2. DLQ-06: 20-iteration OSError retry in load_bundle matching server
   load_state(), or a different (lock-free/rename) concurrency strategy?
3. Confirm the inverted tripwire test (passes-while-broken) gets flipped in the
   same commit as the DLQ-06 fix.
4. Queue metadata note: DLQ-04 implementation_head still reads 0c8d1edd —
   confirm 17b39cbc as the true implementation head (Muse flags, does not edit
   foreign-owned queue line without owner).

EXPECTED_FAILURE_MODE=If the flake survives: --once exits with futures
settled but done_edges unprocessed (dependents never dispatched, run reports
success with work silently undone). If DLQ-06 triggers: PermissionError crash
of the Windows reader during concurrent motor write (fail-stop, no silent
corruption — atomic_write replaces only on close).

CODEX_READY=YES (all fields present, SHA current, tests re-run at HEAD,
no foreign uncommitted code in scope — worktree foreign files
mac_heartbeat.json / central_state.json untouched and unrelated).
PHYSICAL_PENDING=DLQ-06 Windows proof still outstanding (tripwire only).
