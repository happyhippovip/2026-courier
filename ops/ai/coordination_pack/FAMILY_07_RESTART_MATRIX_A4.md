# Family 7: Restart Matrix & A4 Recovery Proof Packet

Status: SPECIFIED & MAPPED
Target: Autonomous Grade A4 (Recovery-Resilient)
Host: Cross-Platform (Mac / Windows / Linux)

---

## 1. Matrix of Recovery Cases

### Case 1: Courier Process Restart (Server Coordinator Crash/Restart)
- **EXPECTED_STATE**: Server reloads JSON state atomically. Reconciled tasks remain `RECONCILED` with `attempts == 1`. In-flight tasks in `DISPATCHED` require worker heartbeat confirmation or transition to `HUMAN_REQUIRED` if state is ambiguous.
- **PROOF_REQUIRED**: Coordinator killed via `SIGTERM`, restarted on same port with same state file. Next claim does NOT re-execute already completed steps.
- **TEST_OR_PHYSICAL**: PHYSICAL (Proven in `run2_proof.json` on Port 8081; `replayed: false`).
- **FAILURE_CONDITION**: Previous step re-dispatched or re-executed (`attempts > 1`), or state lost.

### Case 2: Worker Disappears Mid-Task (Ungraceful Worker Termination)
- **EXPECTED_STATE**: Coordinator detects missing heartbeat after timeout (`HEARTBEAT_TIMEOUT_SECONDS`). Task transitioned to `HUMAN_REQUIRED` with reason `STALE_WORKER_EFFECT_AMBIGUOUS` rather than blind re-dispatch to avoid duplicate real-world effects.
- **PROOF_REQUIRED**: Worker claims task, process is killed (`SIGKILL`) without uploading result. Heartbeat reaper fires. Task marked quarantined.
- **TEST_OR_PHYSICAL**: TEST (`test_reclaim_stale_tasks_quarantines_ambiguous_worker`).
- **FAILURE_CONDITION**: Blind re-queue resulting in duplicate side-effects.

### Case 3: Result Persisted / Reconcile Missing (Crash between `/tasks/result` and `/tasks/verify`)
- **EXPECTED_STATE**: Task status remains `RESULT_RECEIVED`. DurableResult and uploaded artifact references are safely preserved in server store.
- **PROOF_REQUIRED**: Verifier queries `/tasks/pending_verification` after restart, finds pending task, verifies artifact bytes, posts `PASS`, moves task to `RECONCILED`.
- **TEST_OR_PHYSICAL**: TEST & PHYSICAL (Exercised in `run1_canary.py` step 6-8).
- **FAILURE_CONDITION**: Task re-queued to `QUEUED` or result discarded.

### Case 4: READY before Dispatch (Task unlocked, awaiting worker claim)
- **EXPECTED_STATE**: Task status is `QUEUED`, `worker_id == None`, `attempts == 0`.
- **PROOF_REQUIRED**: Process restart preserves `QUEUED` state. First matching worker to poll `/tasks/claim` receives the task and mints `attempt:1`.
- **TEST_OR_PHYSICAL**: TEST (`test_claim_picks_first_queued_step`).
- **FAILURE_CONDITION**: Task dropped or stuck in un-claimable state.

### Case 5: Dispatch Happened / Result Missing (Network dropout or worker crash before result submission)
- **EXPECTED_STATE**: Task status is `DISPATCHED`, bound to `dispatch_id` and `worker_id`. If worker restarts, `daemon.py` inspects `current_task.json`: if phase is `STARTED`, daemon refuses to re-execute and asks server for guidance.
- **PROOF_REQUIRED**: Worker daemon restarted with `current_task.json` in `STARTED` phase. Daemon logs `STARTED without result; refusing duplicate run`.
- **TEST_OR_PHYSICAL**: TEST (`tests/test_mac_worker_recovery.py` & `daemon.py:73`).
- **FAILURE_CONDITION**: Worker unconditionally replays command from scratch.

### Case 6: Temporary Provider Unavailable (503 / Network Error on LLM API)
- **EXPECTED_STATE**: Worker catches transient API error, backs off exponentially (`CRASH_BACKOFF_BASE = 15.0`), retries bounded up to `CRASH_LIMIT = 5`. If limit reached, pauses slot as `PAUSED_ERROR`.
- **PROOF_REQUIRED**: Mock 503 response from LLM; supervisor holds slot in `PAUSED_ERROR` without crashing whole daemon mesh.
- **TEST_OR_PHYSICAL**: TEST (`test_transient_upload_failure_keeps_result_without_reexecution`).
- **FAILURE_CONDITION**: Supervisor spin-loops or drops task.

### Case 7: Stale Result (Late result submission from superseded attempt)
- **EXPECTED_STATE**: Server validates `attempt_id` and `dispatch_id`. If task was already requeued and minted a newer `attempt_id`, late result from previous attempt is rejected with HTTP 400.
- **PROOF_REQUIRED**: Worker posts result with `attempt_id: "w1:attempt:1"` after task was reset to `w1:attempt:2`. Server responds HTTP 400.
- **TEST_OR_PHYSICAL**: TEST (`test_upload_rejects_wrong_binding_name_or_claims`).
- **FAILURE_CONDITION**: Stale result overwrites active attempt.

### Case 8: Identical Duplicate (Idempotent replay of identical result)
- **EXPECTED_STATE**: Server returns `HTTP 200 {"status": "ACK_DUPLICATE"}` or `ACK_RESULT_RECEIVED` without mutating state or re-triggering verifier.
- **PROOF_REQUIRED**: POST `/tasks/result` twice with identical payload. Second response is `ACK_DUPLICATE`.
- **TEST_OR_PHYSICAL**: TEST (`test_p3_server_idempotency.py` & `server/app.py:479`).
- **FAILURE_CONDITION**: Server throws 500 or increments attempts.

### Case 9: Conflicting Duplicate (Conflicting result payload under same dispatch)
- **EXPECTED_STATE**: Server detects hash or payload divergence under identical `dispatch_id` -> rejects with HTTP 400 / 409 conflict.
- **PROOF_REQUIRED**: POST `/tasks/result` with altered `artifacts` or `status` under existing `dispatch_id`. Server rejects.
- **TEST_OR_PHYSICAL**: TEST (`test_result_with_foreign_or_unknown_artifact_id_is_rejected`).
- **FAILURE_CONDITION**: Server overwrites validated result with conflicting payload.
