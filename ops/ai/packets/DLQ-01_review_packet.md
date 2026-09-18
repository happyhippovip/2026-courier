# REVIEW PACKET — DLQ-01 (Codex-ready, COMPLETE)

CURRENT_HEAD=50810001a4eec3bc431a4d3412666f850bf0c3c7
COMMITS_UNDER_REVIEW=none (scripts/agent_handoff_ledger.py unchanged since
7c495f8c; reviewed against code_base_head 0c8d1edd at HEAD 50810001)
TASK_ID=DLQ-01
PRIORITY=P0
OWNER=Google (attester protocol design)

INVARIANT (decided 2026-09-18, MUSE packet QA)=Self-created evidence NEVER
graduates to trusted prior evidence without independent attestation. Concrete:
a MACHINE_ARTIFACT counts toward has_physical_proof only if (a) producer_id and
verifier_id are pairwise distinct (already enforced), AND (b) neither equals any
updated_by recorded in ledger history since that evidence URL first appeared
(writer-independence across updates — the missing check), AND (c) producer /
verifier come from a server-derived attester authority, not self-asserted
strings ("arbitrary" rejection already exists; extend to authenticated
attester identity). Google owns threshold/policy design; (b) is the minimal
enforceable core.

BUG=Two-step self-acceptance via direct ledger writes. update() only rejects
caller-created evidence when the guard CHANGES in the same update
(agent_handoff_ledger.py:743-766). Evidence planted in step 1 (with compliant
distinct producer/verifier IDs and a pre-declared RUNTIME_ARTIFACT PASS citing
the planted URL) becomes "prior evidence" in step 2, when has_physical_proof
is computed from prior_evidence only (:681-688) — promoting to
CANONICAL_ACCEPTED + CLEAN_IDLE=YES with zero independent attestation.

EVIDENCE=/tmp/dlq01_refresh.py run 2026-09-18 at HEAD 50810001 — STEP1
PROVISIONAL, STEP2 CANONICAL_ACCEPTED + CLEAN_IDLE=YES on self-made VALID
MACHINE_ARTIFACT (exit 0, reproduced).

EXACT_FILE=scripts/agent_handoff_ledger.py
EXACT_FUNCTION=update() prior_evidence rule (:681-688) + caller checks
(:743-766) + acceptance branch (:715-726)

REPRODUCER=/tmp/dlq01_refresh.py (tmp ledger, unproven=[]; update1 plants
artifact with RUNTIME_ARTIFACT PASS pre-declared; update2 changes only a
record field with guard=None)

CURRENT_BAD_BEHAVIOR=Step-2 update with no new evidence accepts on planted
self-made proof.
EXPECTED_BEHAVIOR=Step-2 raises LedgerError (unattested prior evidence cannot
satisfy has_physical_proof); ledger stays PROVISIONAL.

TARGETED_TEST_COMMAND=python3 -m pytest tests/test_ledger_self_cert_rejection.py -q
(NEW — Google to implement: two-update self-cert rejection test, fails today)
NEGATIVE_TEST=Legitimate multi-writer evidence (independent producer/verifier
authority) still accepted; existing
tests/test_agent_handoff_ledger.py::test_reject_caller_created_machine_artifact
stays green.
AFFECTED_SUITE=tests/test_agent_handoff_ledger.py
tests/test_ledger_false_green_attack.py
tests/test_ledger_edge_conservation_regression.py (T2: 24 passed 2026-09-18)

REPLAY_CASE=Replayed identical plant blocked by history URL/SHA binding
(:738-758); new-URL plant per cycle is the open hole.
RESTART_CASE=N/A (single-process ledger file; history persists in bundle).
CONCURRENCY_CASE=writer_lock serializes; two writers planting distinct URLs
both enter history — independence check must cover all introducers.
PROVIDER_WAIT_CASE=N/A.

T0=py_compile scripts/agent_handoff_ledger.py OK 2026-09-18
T1=targeted test does not exist yet (this packet orders it)
T2=24 passed (3 ledger files, 2026-09-18)
T3=test_ledger_false_green_attack.py + test_ledger_edge_conservation_regression.py
green (in T2 run); node --test tests/test_execution_truth.mjs pass 1 fail 0

KNOWN_ATTACKS=test_same_update_evidence (blocked), test_replayed_evidence
(blocked), test_wrong_runtime (blocked), test_reject_caller_created_machine_artifact
(same-update only — bypassed cross-update, THIS packet)
FILES_TO_READ=scripts/agent_handoff_ledger.py:634-793
tests/test_agent_handoff_ledger.py:364-520
QUESTIONS_TO_ANSWER=1. Does writer-independence check (b) break the
Google-Antigravity motor path (:159/:386 strip MACHINE_ARTIFACT before update)?
2. Who derives the attester authority for check (c)? 3. Confirm NO production
ledger currently holds CANONICAL_ACCEPTED reached via self-planted evidence.

DEPENDENCIES=Google attester protocol design; no central-state change needed.
CAN_BATCH_WITH=DLQ-02 (same function, shared guard-validation tests)
READY_TO_IMPLEMENT=NO (design owned by Google; packet is complete and attacks live)
