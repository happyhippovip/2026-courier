# REVIEW PACKET — DLQ-07 zero-update preset acceptance via initialize() (Codex-ready, COMPLETE)

CURRENT_HEAD=82bbe0908dfd7db55b5820974f1c0b11e570d7a1
COMMITS_UNDER_REVIEW=none (scripts/agent_handoff_ledger.py unchanged since
7c495f8c-equivalent content; reviewed at HEAD 82bbe090)
TASK_ID=DLQ-07 (new, filed 2026-09-18 by Muse red team round 2)
PRIORITY=P0
OWNER=Google (ledger init/load trust design)

INVARIANT (decided 2026-09-18, MUSE packet QA)=No INIT-to-CANONICAL. The first
CANONICAL_ACCEPTED transition requires at least one UPDATE round-trip after
INIT (revision >= 1 with an UPDATE history entry). Concretely: initialize()
must reject transition_state CANONICAL_ACCEPTED (structural check, no policy
or PKI needed — INIT always starts PROVISIONAL). Load-time verification
(validate_bundle) can then treat revision-0-CANONICAL as malformed. This closes
the zero-history hole that writer-independence (DLQ-01 check b) cannot cover,
since INIT has no history to check against.

BUG=initialize() validates schema, binding, and predicate consistency but
never the attestation checks that update() applies to new evidence
(:743-766: caller-created / producer-verifier / arbitrary-string rejection
live ONLY in update()). A single initialize() call with planted VALID artifact
+ pre-declared all-PASS predicate yields a bundle that is CANONICAL_ACCEPTED
at revision 0 with a one-entry INIT history — and load_bundle() accepts it
clean. One file write (or one CLI init) = acceptance without any process.

EVIDENCE=/tmp/ledger_redteam2.py fam_d run 2026-09-18 at HEAD 82bbe090 —
init transition=CANONICAL_ACCEPTED, loads_clean=True, revision 0 (HOLE).

EXACT_FILE=scripts/agent_handoff_ledger.py
EXACT_FUNCTION=initialize() (:601-631, missing attestation/transition gate) +
validate_bundle() (:335-366, no revision-0-CANONICAL rejection)

REPRODUCER=/tmp/ledger_redteam2.py fam_d (INIT with planted artifact,
all-PASS predicate incl. RUNTIME_ARTIFACT citing planted URL,
transition_state CANONICAL_ACCEPTED; then load_bundle)

CURRENT_BAD_BEHAVIOR=Zero-update CANONICAL_ACCEPTED bundle initializes and
loads without error.
EXPECTED_BEHAVIOR=initialize() raises LedgerError on transition_state !=
PROVISIONAL; load path rejects revision-0 CANONICAL as malformed.

TARGETED_TEST_COMMAND=python3 -m pytest tests/test_ledger_init_rejects_canonical.py -q
(NEW — Google to implement: init-with-CANONICAL rejection test, fails today)
NEGATIVE_TEST=Legitimate INIT flows unaffected — all in-repo initialize()
callers (CLI :992, tests) already start PROVISIONAL; preset CLEAN_IDLE=YES
with PROVISIONAL guard stays rejected (verified blocked 2026-09-18:
"CLEAN_IDLE=YES requires a CANONICAL_ACCEPTED guard").
AFFECTED_SUITE=tests/test_agent_handoff_ledger.py (T2: 24 passed 2026-09-18
for the 3 ledger files incl. attack tests)

REPLAY_CASE=Hand-crafted bundle with valid hash chain + CANONICAL guard is
indistinguishable from processed acceptance at load — the invariant removes
the ambiguity structurally (revision 0 MUST be PROVISIONAL).
RESTART_CASE=N/A (hole is at creation/load, not across restarts).
CONCURRENCY_CASE=writer_lock does not help — single writer creates the preset;
check must be in initialize(), not in locking.
PROVIDER_WAIT_CASE=N/A.

T0=py_compile scripts/agent_handoff_ledger.py OK 2026-09-18
T1=targeted test does not exist yet (this packet orders it)
T2=24 passed (3 ledger files, HEAD 82bbe090-era code)
T3=test_ledger_false_green_attack.py + test_ledger_edge_conservation_regression.py
green; node truth pass 1 fail 0 (same-day runs)

KNOWN_ATTACKS=DLQ-01 two-update laundering (needs 2 updates + history;
THIS packet needs 0 updates + no history — strictly stronger attacker
position, weaker defender visibility); preset CLEAN_IDLE+PROVISIONAL (blocked,
verified); copied-URL replay (blocked :752-758).
FILES_TO_READ=scripts/agent_handoff_ledger.py:601-631,335-366,743-766
QUESTIONS_TO_ANSWER=1. Confirm INIT-must-be-PROVISIONAL vs allowing
INIT-CANONICAL with INIT-time attestation (which authority?). 2. Should
validate_bundle hard-reject revision-0-CANONICAL for old bundles (grandfather
rule)? 3. CLI init reachability: who besides the operator can invoke init
against the production ledger path?

DEPENDENCIES=None (structural check, no policy).
CAN_BATCH_WITH=DLQ-01/DLQ-02 guard-validation tests (same suite, one Google batch)
READY_TO_IMPLEMENT=NO (design confirmation by Google; packet complete, attack live)
