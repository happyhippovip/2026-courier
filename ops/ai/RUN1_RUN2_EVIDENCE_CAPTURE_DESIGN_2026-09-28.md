# RUN_1 / RUN_2 Evidence Capture Design — 2026-09-28

**Role**: `COURIER_RUN1_RUN2_EVIDENCE_CAPTURE_DESIGNER`  
**Host**: MAC (`/Users/user/Downloads/2026-courier`)  
**Provider**: GOOGLE_CLI_OR_MUSE  
**Mode**: READ_ONLY_PREPARATION  
**Date**: 2026-09-28 00:16:30+02:00  
**Status**: CAPTURE_DESIGN_COMPLETE  

---

## 1. RUN_1 Evidence Capture Specifications

### Datum 1: A Execution Count
- **FIELD**: `run1.step_a.execution_count`
- **SOURCE**: Worker execution telemetry / Coordinator `central_state.json`
- **CAPTURE_METHOD**: Parse `task["attempts"]` in `central_state.json` and count invocation records in worker execution log
- **EXPECTED_VALUE**: `1`
- **FAIL_VALUE**: `> 1` or `0`
- **PERSISTENCE_LOCATION**: `run1_proof.json#step_a.attempts`
- **PROOF_BINDING**: Binds `task_id="canary-task-a"` to single execution lifecycle

### Datum 2: A Real Result
- **FIELD**: `run1.step_a.result_payload`
- **SOURCE**: `POST /tasks/result` request body stored in `central_state.json`
- **CAPTURE_METHOD**: Extract `task["result"]` containing `result_id`, `status: "COMPLETED"`, `artifacts`
- **EXPECTED_VALUE**: Object containing non-empty `result_id`, status `"COMPLETED"`, and uploaded artifact references
- **FAIL_VALUE**: Missing `result_id`, empty result object, or `error` field present
- **PERSISTENCE_LOCATION**: `run1_proof.json#step_a.result`
- **PROOF_BINDING**: Cryptographic Result identity `_canonical_hash(result_identity)`

### Datum 3: Task-Owned Expected Hash
- **FIELD**: `run1.step_a.task_expected_sha256`
- **SOURCE**: Initial task definition in Goal Contract (`central_state.json`)
- **CAPTURE_METHOD**: Read `task.get("expected_artifacts", {}).get(path)` or `task.get("expected_sha256")`
- **EXPECTED_VALUE**: Pre-declared 64-char lowercase hex string (e.g. `89828ee566fc9dd853bd3fffd65f9bd4b834d56b6e5a70fcc62c99dfc1bce07b`)
- **FAIL_VALUE**: None, empty string, or derived from worker payload
- **PERSISTENCE_LOCATION**: `run1_proof.json#step_a.expected_sha256`
- **PROOF_BINDING**: Goal Contract immutable declaration; worker cannot forge or override

### Datum 4: Server-Fetched Bytes / Hash
- **FIELD**: `run1.step_a.server_artifact_sha256`
- **SOURCE**: `GET /artifacts/{artifact_id}` response body downloaded by verifier daemon
- **CAPTURE_METHOD**: Verifier downloads raw bytes from staging server store and executes `hashlib.sha256(data).hexdigest()`
- **EXPECTED_VALUE**: Exact 64-char hex match with `task_expected_sha256`
- **FAIL_VALUE**: Hash mismatch or HTTP fetch failure (404/500)
- **PERSISTENCE_LOCATION**: `run1_proof.json#step_a.verified_sha256`
- **PROOF_BINDING**: Verified bytes on staging server store; independent of worker upload hash

### Datum 5: Verification PASS
- **FIELD**: `run1.step_a.verification_verdict`
- **SOURCE**: `POST /tasks/verify` payload from `scripts/courier_verifier.py`
- **CAPTURE_METHOD**: Intercept HTTP request to coordinator and verify recorded `verdict` field in coordinator state
- **EXPECTED_VALUE**: `"PASS"`
- **FAIL_VALUE**: `"FAIL"`, `"UNKNOWN"`, or missing verification record
- **PERSISTENCE_LOCATION**: `run1_proof.json#step_a.verdict`
- **PROOF_BINDING**: Bound to `verifier_id="VERIFIER-CANARY-01"` and `COURIER_VERIFIER_API_KEY`

### Datum 6: Reconciliation Marker
- **FIELD**: `run1.step_a.status`
- **SOURCE**: Coordinator state `central_state.json`
- **CAPTURE_METHOD**: Query `GET /goals/{goal_id}` or inspect `central_state.json` post-verification
- **EXPECTED_VALUE**: `"RECONCILED"`
- **FAIL_VALUE**: `"RESULT_RECEIVED"`, `"DISPATCHED"`, or `"FAILED"`
- **PERSISTENCE_LOCATION**: `run1_proof.json#step_a.status`
- **PROOF_BINDING**: State machine terminal success state for step A

### Datum 7: Timestamp Order Proving B Legal Only After A Verification
- **FIELD**: `run1.order.step_b_dispatch_after_step_a_reconciled`
- **SOURCE**: Event timestamps in coordinator transition log / `central_state.json`
- **CAPTURE_METHOD**: Assert `step_b.dispatched_at >= step_a.reconciled_at` with microsecond precision
- **EXPECTED_VALUE**: `True` (`delta_ms >= 0`)
- **FAIL_VALUE**: `False` (Step B dispatched prior to Step A reconciliation)
- **PERSISTENCE_LOCATION**: `run1_proof.json#order_assertion`
- **PROOF_BINDING**: Contract causal sequencing rule: dependent steps strictly blocked until prerequisite reconciled

### Datum 8: B Dispatch
- **FIELD**: `run1.step_b.dispatch_event`
- **SOURCE**: Coordinator dispatch queue / `central_state.json`
- **CAPTURE_METHOD**: Inspect `task["status"] == "DISPATCHED"` and extract unique `dispatch_id`
- **EXPECTED_VALUE**: Valid UUID prefixed with `dispatch-`, `attempts: 1`
- **FAIL_VALUE**: Missing `dispatch_id`, status remains `QUEUED`, or attempt count > 1
- **PERSISTENCE_LOCATION**: `run1_proof.json#step_b.dispatch_id`
- **PROOF_BINDING**: Single-flight dispatch lease allocated to authorized worker

### Datum 9: B Start
- **FIELD**: `run1.step_b.started_at`
- **SOURCE**: Worker execution trace / `POST /tasks/claim` ACK
- **CAPTURE_METHOD**: Parse worker log timestamp for task execution handler start
- **EXPECTED_VALUE**: ISO 8601 UTC timestamp immediately following dispatch
- **FAIL_VALUE**: None or timestamp preceding dispatch
- **PERSISTENCE_LOCATION**: `run1_proof.json#step_b.started_at`
- **PROOF_BINDING**: Active worker process allocation

### Datum 10: B Completion
- **FIELD**: `run1.step_b.completed_status`
- **SOURCE**: Coordinator `central_state.json` and goal status endpoint
- **CAPTURE_METHOD**: Check `step_b.status == "RECONCILED"` and `goal.status == "DONE"`
- **EXPECTED_VALUE**: `{"step_b": "RECONCILED", "goal": "DONE"}`
- **FAIL_VALUE**: Goal status `ACTIVE`, `BLOCKED`, or step B unverified
- **PERSISTENCE_LOCATION**: `run1_proof.json#goal_completion`
- **PROOF_BINDING**: Terminal acceptance of entire Goal Contract

### Datum 11: HUMAN_RELAY_COUNT
- **FIELD**: `run1.telemetry.human_relay_count`
- **SOURCE**: System interaction logs, stdin stream, operator intervention auditor
- **CAPTURE_METHOD**: Monitor interactive prompt count and operator manual interventions throughout run
- **EXPECTED_VALUE**: `0`
- **FAIL_VALUE**: `> 0`
- **PERSISTENCE_LOCATION**: `run1_proof.json#human_relay_count`
- **PROOF_BINDING**: Autonomy Grade A3/A4 prerequisite: zero human handoffs

### Datum 12: FAILED Execution Count
- **FIELD**: `run1.telemetry.failed_execution_count`
- **SOURCE**: Worker log / error logs / coordinator state
- **CAPTURE_METHOD**: Count tasks with status `FAILED_TERMINAL`, `FAILED_VERIFICATION`, or HTTP 500 error logs
- **EXPECTED_VALUE**: `0`
- **FAIL_VALUE**: `> 0`
- **PERSISTENCE_LOCATION**: `run1_proof.json#failed_execution_count`
- **PROOF_BINDING**: Clean execution proof: 100% first-pass execution success

---

## 2. RUN_2 Evidence Capture Specifications

### Datum 13: A Execution Count Before Restart
- **FIELD**: `run2.pre_restart.step_a.execution_count`
- **SOURCE**: Coordinator `central_state.json` snapshot prior to SIGTERM injection
- **CAPTURE_METHOD**: Read `task["attempts"]` immediately after disk commit of Step A result
- **EXPECTED_VALUE**: `1`
- **FAIL_VALUE**: `!= 1`
- **PERSISTENCE_LOCATION**: `run2_proof.json#pre_restart.step_a.attempts`
- **PROOF_BINDING**: Pre-crash baseline attempt count

### Datum 14: Accepted Result Persistence
- **FIELD**: `run2.pre_restart.step_a.persisted_disk_state`
- **SOURCE**: On-disk `central_state.json` file content
- **CAPTURE_METHOD**: Read file directly from filesystem and compute SHA-256 before killing coordinator process
- **EXPECTED_VALUE**: Valid JSON with `task["status"] == "RECONCILED"` or `"RESULT_RECEIVED"` and valid artifact IDs
- **FAIL_VALUE**: File missing, zero bytes, uncommitted in-memory state, or corrupted JSON
- **PERSISTENCE_LOCATION**: `run2_proof.json#pre_restart.state_file_sha256`
- **PROOF_BINDING**: Durable filesystem boundary

### Datum 15: Checkpoint
- **FIELD**: `run2.checkpoint.marker`
- **SOURCE**: Execution harness event ledger
- **CAPTURE_METHOD**: Record timestamp, coordinator PID, and pre-crash state snapshot
- **EXPECTED_VALUE**: Structured record `{"checkpoint_id": "cutpoint-step-a-done", "pid": <pre_pid>}`
- **FAIL_VALUE**: Missing checkpoint record
- **PERSISTENCE_LOCATION**: `run2_proof.json#checkpoint`
- **PROOF_BINDING**: Causal cutoff boundary

### Datum 16: Controlled Restart Marker
- **FIELD**: `run2.restart.signal_event`
- **SOURCE**: Process supervisor logs and OS signal return
- **CAPTURE_METHOD**: Send `SIGTERM` (`kill -15 <pid>`); assert process termination; launch new coordinator on Port 8081; capture new PID
- **EXPECTED_VALUE**: `{"signal": "SIGTERM", "terminated": true, "new_pid": <new_pid>, "pids_distinct": true}`
- **FAIL_VALUE**: Process failed to terminate, unclean exit code, or port collision on restart
- **PERSISTENCE_LOCATION**: `run2_proof.json#restart_marker`
- **PROOF_BINDING**: Controlled failure injection proof

### Datum 17: A Execution Count After Restart
- **FIELD**: `run2.post_restart.step_a.execution_count`
- **SOURCE**: Reloaded `central_state.json` and worker logs post-coordinator revival
- **CAPTURE_METHOD**: Query `GET /goals/{goal_id}` on revived server and verify `attempts` field
- **EXPECTED_VALUE**: `1` (Identical to pre-restart value)
- **FAIL_VALUE**: `> 1` (Attempt inflation) or reset to `0`
- **PERSISTENCE_LOCATION**: `run2_proof.json#post_restart.step_a.attempts`
- **PROOF_BINDING**: Zero attempt inflation invariant

### Datum 18: No A Replay
- **FIELD**: `run2.post_restart.step_a.replayed`
- **SOURCE**: Worker execution trace / coordinator dispatch queue
- **CAPTURE_METHOD**: Assert that `canary-task-a` was NEVER re-dispatched to worker and worker handler executed exactly 0 times post-crash
- **EXPECTED_VALUE**: `false`
- **FAIL_VALUE**: `true` (Step A re-dispatched or re-executed)
- **PERSISTENCE_LOCATION**: `run2_proof.json#post_restart.step_a.replayed`
- **PROOF_BINDING**: Core A4 Invariant: completed work is never repeated after crash

### Datum 19: Reconciliation After Restart
- **FIELD**: `run2.post_restart.step_a.status`
- **SOURCE**: Revived coordinator `central_state.json`
- **CAPTURE_METHOD**: Query task status post-reload
- **EXPECTED_VALUE**: `"RECONCILED"`
- **FAIL_VALUE**: `"PENDING"`, `"QUEUED"`, `"FAILED"`, or missing
- **PERSISTENCE_LOCATION**: `run2_proof.json#post_restart.step_a.status`
- **PROOF_BINDING**: Durability of verified state across abrupt process death

### Datum 20: B Automatic Start
- **FIELD**: `run2.post_restart.step_b.auto_dispatched`
- **SOURCE**: Coordinator dispatch queue post-restart
- **CAPTURE_METHOD**: Verify that `canary-task-b` transitioned from `QUEUED` to `DISPATCHED` autonomously without operator prompt
- **EXPECTED_VALUE**: `true` (`human_interventions == 0`)
- **FAIL_VALUE**: `false` (Coordinator stalled, required human prompt to unblock)
- **PERSISTENCE_LOCATION**: `run2_proof.json#post_restart.step_b.auto_dispatched`
- **PROOF_BINDING**: Forward-progress recovery invariant

### Datum 21: B Completion
- **FIELD**: `run2.post_restart.step_b.status`
- **SOURCE**: Final goal status from revived coordinator
- **CAPTURE_METHOD**: Query `GET /goals/{goal_id}` and assert `{"step_b": "RECONCILED", "goal": "DONE"}`
- **EXPECTED_VALUE**: `"RECONCILED"` with goal status `"DONE"`
- **FAIL_VALUE**: Step B failed or goal incomplete
- **PERSISTENCE_LOCATION**: `run2_proof.json#post_restart.goal_status`
- **PROOF_BINDING**: End-to-end post-restart goal success
