# ATTACK PACKET — DLQ-08 hung task wedges motor, no bounded drain timeout (COMPLETE)

CURRENT_HEAD=82bbe0908dfd7db55b5820974f1c0b11e570d7a1
COMMITS_UNDER_REVIEW=none (scripts/courier_continue.py behavior reviewed at
HEAD 82bbe090; DLQ-04 fix 17b39cbc is context, not cause)
TASK_ID=DLQ-08 (new, filed 2026-09-18 by Muse motor torture)
PRIORITY=P1
OWNER=foreign/motor (coordinate, FOREIGN-ACTIVE file — PACKET ONLY, do not race)

INVARIANT (required)=ONE HUNG TASK != WEDGED MOTOR. --once MUST exit after
futures settle OR a bounded drain timeout even when a task thread never
returns. Concretely: future.result() needs a per-call timeout plus a loop
wall-clock deadline (time.monotonic), after which the hung edge is recorded
blocked (first_causal_blocker HUNG_TASK) and the run exits non-zero or
continues with remaining work — never parks forever.

BUG=courier_continue.py:527 calls future.result() with NO timeout, and the
main loop has NO wall-clock bound (grep: no deadline/drain/monotonic anywhere;
mock_iters counts iterations only under MOCK_SHA). One hung task thread parks
the drain loop indefinitely: --once never exits, dependents never dispatch,
no ledger record is written. This is the unimplemented second half of the
DLQ-04 invariant ("...or bounded drain timeout"), which the DLQ-04 fix did not
add.

EVIDENCE=Code fact (bare :527 result(), zero deadline identifiers in file) +
/tmp/motor_hang_bound.py run 2026-09-18: owned-PID child running the exact
:527 call pattern against a 300s sleeper did not return within the 8s wrapper
deadline (mechanism proven, bounded, no foreign processes).

EXACT_FILE=scripts/courier_continue.py
EXACT_FUNCTION=main() done_edges drain loop (:522-552, result at :527) +
executor setup (:414, ThreadPoolExecutor max_workers=5, threads
unkillable by design)

REPRODUCER=/tmp/motor_hang_demo.py (exact :527 pattern) + /tmp/motor_hang_bound.py
(8s owned-PID wrapper proving indefinite block)

CURRENT_BAD_BEHAVIOR=Hung task parks --once forever with no record, no exit,
no timeout signal.
EXPECTED_BEHAVIOR=Per-result timeout fires, hung edge recorded blocked with
HUNG_TASK blocker, run exits bounded (non-zero) with dependents' state intact.

TARGETED_TEST_COMMAND=python3 -m pytest tests/test_motor_hung_task_bound.py -q
(NEW — owner to implement: sleeper-task run must exit bounded with HUNG_TASK
blocker; hangs forever today)
NEGATIVE_TEST=Healthy tasks still settle normally with identical results;
timeout path never triggers when tasks return within budget; no orphan threads
accumulate across bounded exits (owned-PID accounting).
AFFECTED_SUITE=tests/test_courier_continue.py (15/15 green at HEAD — none
covers hang)

REPLAY_CASE=Restart after wedge: hung edge has no checkpoint (never returned)
→ resume must re-dispatch, never assume completion.
RESTART_CASE=Crash/kill of wedged motor leaves ledger untouched (fail-closed);
post-fix bounded exit writes HUNG_TASK blocker durably before exit.
CONCURRENCY_CASE=One hung thread must not consume the 5-worker pool forever:
timeout releases the slot; other edges continue (ONE BLOCKED TASK != BLOCKED
MOTOR).
PROVIDER_WAIT_CASE=WAITING_PROVIDER edges are short-lived mock returns today;
a provider that never recovers degrades into this same wedge — shared deadline
covers both.

T0=py_compile scripts/courier_continue.py OK (same-day)
T1=targeted test does not exist yet (this packet orders it)
T2=test_courier_continue.py 15/15 green (no hang coverage — the gap)
T3=ledger attack tests green (unaffected area)

KNOWN_ATTACKS=Early-exit flake (DLQ-04, fixed); infinite-park via hang (THIS
packet, live); MOCK_SHA iteration games (bounded-drain design, mock-only).
FILES_TO_READ=scripts/courier_continue.py:410-420,522-552
QUESTIONS_TO_ANSWER=1. Per-result timeout value + loop wall-clock bound
(owner policy)? 2. HUNG_TASK as new blocker string — accepted taxonomy?
3. Bounded exit code: non-zero exit, or settle-with-blocker + exit 0?
4. ThreadPoolExecutor stays (threads unkillable — slot leak per hang) or move
to process pool with terminate?

DEPENDENCIES=Owner (foreign/motor) implementation; ledger-side HUNG_TASK
blocker acceptance if new string introduced.
CAN_BATCH_WITH=DLQ-04 follow-up verification (same loop, same suite)
READY_TO_IMPLEMENT=YES (with owner — no design unknowns except policy values)
