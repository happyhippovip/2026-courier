# REVIEW PACKET — DLQ-03 (Codex-ready, COMPLETE — contract-test order)

CURRENT_HEAD=50810001a4eec3bc431a4d3412666f850bf0c3c7
COMMITS_UNDER_REVIEW=none (scripts/agent_handoff_ledger.py unchanged since
7c495f8c; scripts/courier_continue.py retry loop :531-545 reviewed against
code_base_head 0c8d1edd at HEAD 50810001)
TASK_ID=DLQ-03
PRIORITY=P1
OWNER=Google (decision + contract test)

INVARIANT (DECIDED 2026-09-18, MUSE packet QA)=DOCUMENTED duplicate-result
contract, raise-at-storage: (1) IDENTICAL same-revision resubmission raises
LedgerError("update makes no meaningful change") — no state transition, no
revision increment, bundle bytes unchanged; callers treat THIS error string as
successful-settle (idempotent ACK at protocol layer, raise at storage layer).
(2) STALE-revision contradictory update raises LedgerError("revision
conflict: ...") and the authoritative stored result is never overwritten;
callers retry with backoff on THIS error string. Rationale: motor retry loop
already implements exactly this split (courier_continue.py:537-544: break on
"meaningful change", sleep+retry on "revision conflict"); the decision codifies
de-facto behavior so no caller can mistake a raise for data loss or a settle
for acceptance.

BUG (mild, contract gap — NOT a live hole)=Semantics were undocumented:
identical retry raising (instead of silent ACK) could be misread by a future
caller as failure, and conflict-retry could be misread as safe to force.
Verified fail-closed on both branches; nothing to fix in storage, contract to
lock with a test.

EVIDENCE=/tmp/dlq03_refresh.py run 2026-09-18 at HEAD 50810001 — (a) identical
retry raised "no meaningful change", revision + bytes unchanged; (b) stale
contradictory update raised "revision conflict: expected 1, current 2",
authoritative TASKS_COMPLETED=5 kept (exit 0, contract holds).

EXACT_FILE=scripts/agent_handoff_ledger.py + scripts/courier_continue.py
EXACT_FUNCTION=update() no-change raise (:768-770) vs revision conflict
(:653-657); motor retry split (:537-544)

REPRODUCER=/tmp/dlq03_refresh.py (init tmp ledger; update TASKS_COMPLETED=1;
identical retry at same revision; advance to 5; stale contradictory write of 9
at old revision)

CURRENT_BAD_BEHAVIOR=Contract implicit only — a new caller matching on the
wrong substring (or swallowing all LedgerError as settle) would corrupt retry
semantics.
EXPECTED_BEHAVIOR=Committed contract test pins both branches; storage code
unchanged.

TARGETED_TEST_COMMAND=python3 -m pytest tests/test_ledger_duplicate_semantics_contract.py -q
(NEW — Google to implement, 3 asserts: identical-retry raises + bytes
unchanged; stale-contradictory raises conflict; authoritative value kept.
Ready to implement YES — contract-test only, no Ledger/Motor edits.)
NEGATIVE_TEST=Contradictory payload never overwrites authoritative result
(assert (b) above); genuine new update at current revision still advances.
AFFECTED_SUITE=tests/test_agent_handoff_ledger.py
tests/test_ledger_edge_conservation_regression.py (T2: 24 passed 2026-09-18)

REPLAY_CASE=Re-delivery of an already-applied result (at-least-once transport)
hits branch (1) → settle, never double-applies.
RESTART_CASE=Crash between write and ACK replays the same update → branch (1)
settles idempotently; crash with concurrent writer advance → branch (2)
retries.
CONCURRENCY_CASE=Two writers racing: loser gets revision conflict, re-reads,
re-bases — no lost update, no silent overwrite.
PROVIDER_WAIT_CASE=N/A.

T0=py_compile scripts/agent_handoff_ledger.py + scripts/courier_continue.py OK
T1=targeted contract test does not exist yet (this packet orders it)
T2=24 passed (3 ledger files, 2026-09-18)
T3=test_ledger_false_green_attack.py + test_ledger_edge_conservation_regression.py
green (in T2 run); node --test tests/test_execution_truth.mjs pass 1 fail 0

KNOWN_ATTACKS=Double-apply via identical replay (blocked — branch 1);
stale-overwrite via old revision (blocked — branch 2, edge-conservation tests
green).
FILES_TO_READ=scripts/agent_handoff_ledger.py:651-670,768-793
scripts/courier_continue.py:531-545
QUESTIONS_TO_ANSWER=1. Confirm error-substring matching ("meaningful change" /
"revision conflict") as the stable caller contract vs introducing typed error
codes. 2. Retry budget (5 x ~0.5-1.5s) sufficient or bounded-drain timeout
wanted (DLQ-04 adjacency)? 3. Any second caller of update() besides
courier_continue.py:159/:386 and feed_evidence.py that needs the same split?

DEPENDENCIES=None (test-only).
CAN_BATCH_WITH=DLQ-01/DLQ-02 guard-validation tests (same suite, one Google batch)
READY_TO_IMPLEMENT=YES (contract test only)

## IMPLEMENTATION FORGE + CLOSURE (2026-09-18, HEAD d00a00a8 — status update, review above unchanged)

STATUS=CLOSED END-TO-END. Google implemented
tests/test_ledger_duplicate_semantics_contract.py (commit 20ca0601); Muse
independently re-ran green and assertion-reviewed it against the decided
invariant: identical-retry raises + bytes unchanged, genuine update advances,
stale-contradictory raises conflict + authoritative value kept. Queue status:
IMPLEMENTED_AND_VERIFIED (confirmed, not edited by Muse).
MIGRATION: contract strings "makes no meaningful change" / "revision conflict"
are now pinned by a committed test AND matched by scripts/courier_continue.py
:537-544. Any future rename of these strings must update the motor matcher in
the same commit — recorded here as the standing constraint.
AFFECTED_CALLERS: courier_continue.py:159/:384 (via update_ledger retry split),
feed_evidence.py (no handler — manual one-shot, fail-closed propagation is
correct there), CLI update (LedgerError surfaces to operator, correct).
No Codex decision was pending on this item; none invented.
WAITING_FOR_CODEX_DECISION=(none — item closed, no placeholders outstanding)
GOOGLE_ZERO_ARCHAEOLOGY=YES (nothing left to implement).

## CURRENT RED-TEAM RESULT — 2026-09-18

CODE_SHA=b0f6cec5e7a8e3ca64c9039792d239d2e67fe5ea

Storage semantics remain correct, but caller semantics are not yet typed.
`scripts/courier_continue.py` still branches on the English substrings
`"meaningful change"` and `"revision conflict"` in `str(e)`.  The landed
contract test asserts those message fragments, so it preserves the fragile
coupling rather than proving stable machine-readable behavior.

CURRENT_SAFE_CLAIM=Identical replay does not mutate bytes or revision; stale
contradictory update does not overwrite authoritative state.  The current
caller settles/retries correctly only while the exact message wording remains
unchanged and unwrapped.

MINIMUM_GOOGLE_REPAIR=Give `LedgerError` a stable code (at minimum
`NO_MEANINGFUL_CHANGE` and `REVISION_CONFLICT`) or use narrow subclasses.
`courier_continue.py` must branch on that typed value.  Human-readable messages
remain free to change.  Preserve the existing five-attempt bound and storage
behavior.

TEST_GOOGLE_MUST_ADD=Change/wrap/localize the human-readable messages while
asserting that identical replay still settles and revision conflict still
retries; unknown error codes must fail closed and must not be treated as an
idempotent ACK.

STATUS=REOPENED_FOR_TYPED_CALLER_CONTRACT; duplicate storage semantics remain
verified and must not be rewritten.
