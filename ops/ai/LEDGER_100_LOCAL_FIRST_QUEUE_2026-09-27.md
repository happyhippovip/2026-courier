# Ledger 100 Local-First Queue — 2026-09-27

Status: ACTIVE LOGICAL QUEUE
Purpose: provide 100 distinct, durable, mostly local-CPU tasks that Google CLI and Muse can claim without broad rediscovery.

## Operating model

- This file defines 100 LOGICAL tasks. It does NOT require 100 active physical processes.
- Workers are READ_ONLY against application source unless a newer durable task explicitly grants a distinct writer scope.
- Claims/results live in host-local scratch, not the shared source checkout.
- Completed task IDs do not repeat unless their RETEST_TRIGGER changes.
- Prefer deterministic local commands/tests over model analysis whenever possible.
- MAX_HEAVY_JOBS=1 per host.
- Never broad-scan the repo.
- Never run full test suites unless a task explicitly says so.
- Windows Antigravity Central Writer remains the final-candidate application source writer.

## Host-local scratch

Windows:
C:\Users\lol\courier_work\ledger100\

Mac:
 /Users/user/Downloads/courier_work/ledger100/

Layout:
claims/
results/
checkpoints/

One live claim per task.
Use an atomic host-native directory create for claims when available.
A result file marks the task complete unless RETEST_TRIGGER changed.

## Common exact inputs

Use only as needed:
- ops/ai/WALL_SYSTEM.md
- ops/ai/WALL_QUEUE_CURRENT.md
- ops/ai/WALL_TASK_PACKET_SCHEMA.md
- ops/ai/RETURNED_RESULT_POLICY.md
- ops/ai/COURIER_SESSION_STATE_2026-09-26.json
- ops/ai/GOOGLE_PRE_CODEX_GATE_2026-09-27.md
- ops/ai/NIGHT_QUEUE_NONINTERFERENCE_AND_COST_POLICY_2026-09-27.md
- ops/ai/DEVICE_ADAPTIVE_MOTOR_ADMISSION_2026-09-27.md
- docs/COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md
- scripts/integration_contract.py
- scripts/courier_verifier.py
- server/app.py
- tests/test_artifact_upload_flow.py
- tests/test_p3_server_idempotency.py
- tests/test_result_identity_binding.py
- existing durable queue/result summaries

## Local-first execution law

For each task, prefer this order:

1. git metadata / exact file read
2. grep/ripgrep exact symbol lookup
3. Python stdlib parser/check
4. py_compile for exact Python modules
5. one exact pytest node or one exact test file when authorized
6. hashing / JSON parsing / schema validation locally
7. model reasoning only for interpretation, synthesis, contradiction classification, or packet generation

Do not ask the model to do work a deterministic local command can prove.

## Result contract

TASK_ID=
STATUS=PASS|FAIL|BLOCKED|RETEST_REQUIRED
INPUTS_READ=
LOCAL_COMMANDS=
TESTS_RUN=
EVIDENCE=
FINDING=
CENTRAL_WRITER_INPUT=
RETEST_TRIGGER=
DO_NOT_REPEAT=
NEXT_DEPENDENCY=

---

# A — Identity chain / schema truth

L100-001 Goal-ID field map
L100-002 Goal Contract fingerprint map
L100-003 Task-ID field map
L100-004 Attempt-ID field map
L100-005 Claim/lease identity map
L100-006 Dispatch-generation identity map
L100-007 Provider-route identity map
L100-008 Execution-ID field map
L100-009 Result-ID/fingerprint map
L100-010 Verification/Reconciliation identity chain

Done condition for 001-010:
exact field/source/result references + missing/ambiguous classification.

# B — Result identity / duplicate equivalence

L100-011 Canonical identical-result fingerprint inputs
L100-012 identical replay same attempt same dispatch
L100-013 replay persistence/reload
L100-014 changed status rejection
L100-015 changed worker rejection
L100-016 changed attempt rejection
L100-017 changed dispatch generation rejection
L100-018 changed artifact result rejection
L100-019 stale result overwrite prevention
L100-020 contradictory duplicate classification

Done:
exact code/test evidence or exact missing targeted test packet.

# C — Trusted content / artifact integrity

L100-021 task-owned expected_sha256 source
L100-022 expected hash survives task storage
L100-023 expected hash survives prepare/dispatch
L100-024 expected hash survives pending verification
L100-025 correct server bytes PASS
L100-026 wrong server bytes FAIL
L100-027 worker expected hash cannot authorize PASS
L100-028 worker omission cannot bypass task expectation
L100-029 no task expectation remains legacy only
L100-030 malformed/ambiguous artifact target fails closed

RETEST_TRIGGER for candidate-sensitive tasks:
FINAL_SHA_CHANGED

# D — Persistence / durability

L100-031 result persisted before reconciliation
L100-032 persistence atomicity exact path
L100-033 restart reload of accepted result
L100-034 restart reload of pending result
L100-035 stale persistence record handling
L100-036 duplicate persisted result idempotency
L100-037 partial/corrupt state fail-closed behavior
L100-038 missing state recovery semantics
L100-039 fsync/atomic replace evidence where relevant
L100-040 candidate/runtime fingerprint persistence

# E — Reconciliation / NEXT_READY

L100-041 validation-before-reconcile ordering
L100-042 contract-check-before-accept ordering
L100-043 reconciliation idempotency
L100-044 dependency completion update
L100-045 READY recomputation
L100-046 eligibility filter
L100-047 worker selection boundary
L100-048 automatic dispatch boundary
L100-049 queue-empty truthful IDLE
L100-050 UNKNOWN execution reconciliation rule

# F — Claim / lease / concurrency

L100-051 atomic single-claim behavior
L100-052 competing claims same task
L100-053 lease expiry rule
L100-054 stale claim reclaim rule
L100-055 live claim non-steal rule
L100-056 writer ownership one mutable scope
L100-057 result owner/worker binding
L100-058 attempt-to-execution one-active invariant
L100-059 claim persistence across session change
L100-060 claim cleanup/release idempotency

# G — Restart / recovery matrix

L100-061 Courier process restart
L100-062 worker disappears
L100-063 result persisted reconcile missing
L100-064 READY before dispatch restart
L100-065 dispatch happened result missing
L100-066 provider temporarily unavailable
L100-067 stale result after restart
L100-068 identical duplicate after restart
L100-069 conflicting duplicate after restart
L100-070 no A re-execution after restart

Done:
EXPECTED_STATE / LOCAL_TEST_OR_PHYSICAL / EVIDENCE_REQUIRED / GAP.

# H — Queue / Harvester / do-not-repeat

L100-071 result contract validation
L100-072 result fingerprint dedup
L100-073 evidence refs attach
L100-074 contradiction handling
L100-075 stale result handling
L100-076 RETEST_TRIGGER semantics
L100-077 do-not-repeat fingerprint semantics
L100-078 queue-generation supersession
L100-079 dependency unlock after harvest
L100-080 automatic refill/next READY

# I — Session / provider / cost / context

L100-081 /clear continuity
L100-082 fresh-session continuity
L100-083 manual provider/account session continuity
L100-084 completed task survives account change
L100-085 no duplicate execution after account change
L100-086 minimal read budget enforcement
L100-087 no broad census guard
L100-088 no repeated unchanged reads guard
L100-089 queue empty => no idle analysis
L100-090 context checkpoint -> clear -> resume packet

# J — Resource / proof / final synthesis

L100-091 requested/admitted/active/guarded wall fields
L100-092 workload-class admission
L100-093 MAX_HEAVY_JOBS invariant
L100-094 pressure backoff behavior
L100-095 source/build/runtime fingerprint binding
L100-096 Proof Card required fields
L100-097 Covered Surface / revalidation trigger
L100-098 exact 12-case matrix synthesis from prior results
L100-099 Ledger freeze blocker synthesis
L100-100 Pre-Codex Ledger handoff synthesis

L100-098 inputs:
results 021-030 + 011-020 + current FINAL_SHA evidence only.

L100-099 inputs:
completed identity/persistence/reconcile/recovery result summaries only.

L100-100 inputs:
results 001-099 summaries only; no new source scan.

Required L100-100 output:

LEDGER_READY=
LEDGER_FREEZE_BLOCKERS=
TWELVE_CASE_MATRIX_COMPLETE=
RESTART_PREP_COMPLETE=
HARVESTER_READY=
NEXT_READY_RULE_READY=
SESSION_CONTINUITY_READY=
COST_GUARD_READY=
FINAL_SHA=
PRE_CODEX_LEDGER_SIDE_READY=
OPEN=
BLOCKED=
NEXT=

## Queue end

When L100-100 is complete:
do not create L100-101 automatically.

If FINAL_SHA changes:
only tasks whose RETEST_TRIGGER is FINAL_SHA_CHANGED are reopened.

If no READY task exists:
harvest results, recompute dependencies once, then truthful IDLE.
