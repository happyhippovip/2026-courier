# REVIEW PACKET — DLQ-02 (Codex-ready, COMPLETE)

CURRENT_HEAD=50810001a4eec3bc431a4d3412666f850bf0c3c7
COMMITS_UNDER_REVIEW=none (scripts/agent_handoff_ledger.py unchanged since
7c495f8c; reviewed against code_base_head 0c8d1edd at HEAD 50810001)
TASK_ID=DLQ-02
PRIORITY=P0
OWNER=Google (freshness policy design)

INVARIANT (decided 2026-09-18, MUSE packet QA)=Freshness bound enforced on
physical proof. Concrete: a MACHINE_ARTIFACT counts toward has_physical_proof
only if (a) its observed_at is within a bounded recency window of server time
at the update that FIRST introduces it (window length is Google policy; probe
uses 2020-01-01 vs 2026-09-18 as the must-reject case), AND (b) observed_at is
monotonic non-decreasing for a given evidence URL across updates (no
back-dating after introduction). Format validation (UTC second precision,
:244-247) stays as-is; recency is the missing check.

BUG=Stale-dated VALID artifact accepted. validate_guard checks observed_at
FORMAT only (:244-247); has_physical_proof (:682-688) checks source_type /
evidence_sha / runtime_binding / validity but never observed_at. A 2020-01-01
VALID artifact bound to the current SHA/runtime promotes to CANONICAL_ACCEPTED
in the step-2 pattern (same mechanics as DLQ-01).

EVIDENCE=/tmp/dlq02_refresh.py run 2026-09-18 at HEAD 50810001 — 2020-dated
VALID artifact planted step 1 (PROVISIONAL), step 2 with no new evidence →
CANONICAL_ACCEPTED + CLEAN_IDLE=YES (exit 0, reproduced).

EXACT_FILE=scripts/agent_handoff_ledger.py
EXACT_FUNCTION=update() has_physical_proof block (:682-688) + observed_at
format-only validation (:244-247)

REPRODUCER=/tmp/dlq02_refresh.py (reuses /tmp/dlq01_refresh.py fixtures;
plants observed_at 2020-01-01T00:00:00Z VALID bound artifact; step 2 advances
record-only)

CURRENT_BAD_BEHAVIOR=Six-year-stale evidence accepted as current physical proof.
EXPECTED_BEHAVIOR=Step-1 plant raises LedgerError (observed_at outside recency
window) or step-2 promotion refuses stale proof; ledger stays PROVISIONAL.

TARGETED_TEST_COMMAND=python3 -m pytest tests/test_ledger_freshness_rejection.py -q
(NEW — Google to implement: stale-date rejection test, fails today)
NEGATIVE_TEST=Fresh VALID evidence (observed_at within window, bound to current
SHA/runtime) still accepted and still promotes.
AFFECTED_SUITE=tests/test_agent_handoff_ledger.py
tests/test_ledger_false_green_attack.py
tests/test_ledger_edge_conservation_regression.py (T2: 24 passed 2026-09-18)

REPLAY_CASE=Re-introducing the same stale URL with a freshened observed_at is a
copied-proof variant — monotonicity check (b) plus SHA/history binding must
reject it.
RESTART_CASE=N/A (bundle history carries observed_at durably).
CONCURRENCY_CASE=Server time (not writer claim) is the recency reference;
concurrent introducers share the same clock.
PROVIDER_WAIT_CASE=N/A.

T0=py_compile scripts/agent_handoff_ledger.py OK 2026-09-18
T1=targeted test does not exist yet (this packet orders it)
T2=24 passed (3 ledger files, 2026-09-18)
T3=test_ledger_false_green_attack.py + test_ledger_edge_conservation_regression.py
green (in T2 run); node --test tests/test_execution_truth.mjs pass 1 fail 0

KNOWN_ATTACKS=DLQ-01 plant (fresh-dated variant, THIS packet's sibling);
no existing test submits an ancient observed_at (gap confirmed — no 2020-dated
evidence in tests/test_agent_handoff_ledger.py).
FILES_TO_READ=scripts/agent_handoff_ledger.py:219-266,634-736
tests/test_agent_handoff_ledger.py:292-364
QUESTIONS_TO_ANSWER=1. Recency window length and whose clock (server update
time REQUIRED)? 2. Grandfather rule for pre-policy VALID artifacts in existing
bundles? 3. Does monotonicity (b) interfere with legitimate re-observation of
long-lived artifacts?

DEPENDENCIES=Google freshness policy (window length, clock authority).
CAN_BATCH_WITH=DLQ-01 (same function, shared guard-validation tests)
READY_TO_IMPLEMENT=NO (policy owned by Google; packet is complete and attacks live)
