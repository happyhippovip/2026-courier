# GLEDGER-101 Result — Canonical Entity Chain

TASK_ID=GLEDGER-101
STATUS=PROVEN (by prior harvested evidence, refs below; daemon enum abstracted — see MISSING)
HOST=MAC
PROVIDER=GOOGLE
INPUTS_READ=ops/ai/LEDGER_FINISH_QUEUE_30_2026-09-27.md (task definition only; all entity evidence reused from prior harvested reads: server/app.py, scripts/integration_contract.py, scripts/artifact_store.py, scripts/courier_verifier.py, scripts/mac_worker/runtime_state.py head, tests/test_p3_server_idempotency.py, tests/test_artifact_upload_flow.py, PHYS proof bundle)
RESULTS_REUSED=L1/L2/L3/P4/P5 overnight evidence; POST200-021 12-case classification (RECONCILED); PHYS-002/003 proof bundle (RUN_1/RUN_2 attested)

## Canonical chain (each entity: canonical ID, parent, single writer)

1. GOAL — id `goal-<hash8>` (e.g. `goal-d0a02c0e`). Root (created from workflow_plan + metadata). Writer: intake/validate (`validate_goal_workflow`). Children: TASKs.
2. CONTRACT — no stored ID; the rule set (`scripts/integration_contract.py`: goal validation + `validate_durable_result`). Inputs: GOAL workflow, RESULT shapes. Output: accept/reject decisions. Single owner: contract module (called by server claim path, verifier, daemons — never rewritten by workers).
3. TASK — id `task-<slug>-<hash4>` (e.g. `canary-task-a`). Parent: GOAL (`goal_id`). Fields: `task_id, goal_id, worker_id, attempt, dispatch_id, status, result`. Writer: server dispatch. Children: ATTEMPTs, CLAIMs.
4. ATTEMPT — integer ≥1 scoped to (`task_id`). Parent: TASK. Writer: server (incremented only via `/tasks/{id}/resume` retry from HUMAN_REQUIRED/FAILED_VERIFICATION/FAILED_TERMINAL). No attempt reuse across retries.
5. CLAIM/LEASE — binding `(task_id, worker_id, attempt, dispatch_id, claimed_at)`; server holds DISPATCHED + `dispatch_last_seen`. Parent: TASK + ATTEMPT. Writer: server claim path. Recovery owner: stale worker's DISPATCHED tasks → HUMAN_REQUIRED (quarantine, never auto-replay); resume requires explicit retry action.
6. DISPATCH — id `dispatch-<uuidhex12>`, minted fresh per claim. Parent: CLAIM (same binding). Rule: superseded (attempt, dispatch) pairs are unbindable — result submit with mismatched attempt/dispatch → 400/409.
7. EXECUTION — worker-side run record (`scripts/mac_worker/runtime_state.py`: atomic JSON + STOP fencing). Parent: DISPATCH. Lifecycle: claimed → running → terminal (succeeded/failed); transport/5xx retry with identical payload, 4xx kept-as-evidence without retry, exceptions not retried (per recovery tests). Exact daemon state-enum names NOT re-verified here — see MISSING.
8. RESULT — id `result-<canonical-hash16>` on local build path (content-derived); server remote path accepts non-empty string WITHOUT recompute (observed asymmetry — duplicate-equivalence boundary, see GLEDGER-107 note). Fields: `goal_id, task_id, worker_id, attempt, dispatch_id, result_id, artifacts[], completed_at`. Parent: EXECUTION + DISPATCH + TASK. Writer: worker only. `expected_sha256`, when present, travels inside `artifacts[]` refs (worker-supplied; verified against server bytes only — ownership binding open, POST200-021 cases 1/4).
9. VERIFY — record `{task_id, result_id, verifier_id != worker_id, verdict PASS|FAIL, artifacts == result.artifacts, timestamp}`. Parent: RESULT. Writer: independent verifier only (self-certification → 400). No evidence → no PASS.
10. RECONCILE — transitions: RESULT_RECEIVED → PASS → RECONCILED (+ goal `current_step_index`+1; DONE when plan exhausted) / FAIL → FAILED_VERIFICATION (retryable via resume) or FAILED_TERMINAL. Duplicate resubmission of identical (dispatch_id, result_id, status) → ACK_DUPLICATE; any changed status/worker/attempt/dispatch → 409/400, never silent ACK (b1 semantics; b2's status-drop correctly rejected). Writer: server.
11. NEXT_READY — next claim serves `workflow_plan[current_step_index]` iff QUEUED, else `task=None`. Parent: RECONCILE (step index). Stop conditions: goal BLOCKED, no QUEUED steps, human/money/safety gate. Liveness is poll-driven both halves; no push channel.

## Ownership (no ambiguous ownership)
Exactly one writer per entity: GOAL intake, TASK/DISPATCH/CLAIM/RECONCILE/NEXT_READY server, EXECUTION/RESULT worker, VERIFY independent verifier, CONTRACT module (rules, not data). Workers never write server state except via result-submit/verify endpoints; server never invents execution content; verifier never writes results.

MISSING=Exact daemon runtime_state state-enum member names (abstracted from recovery-test behavior + module head; needs one targeted read for GLEDGER-106 to normatively list); server-path result_id canonicalization rule (open, POST200-021 cases 1/4/12).
BLOCKER=None in-lane.
NEXT_DEPENDENCY=GLEDGER-102 (Goal/Contract fields), GLEDGER-107 (duplicate-equivalence boundary uses §8/§10 above).
DO_NOT_REPEAT_FINGERPRINT=gledger-101-entity-chain-complete

DO_NOT_REPEAT_FINGERPRINT=sha256-8ac5178e74abbb0d

DO_NOT_REPEAT_FINGERPRINT=sha256-4436e25c5e2bd672

DO_NOT_REPEAT_FINGERPRINT=sha256-fd2924e44ada8429
