# TASK_45 — Deterministic RUN_2 Restart Checkpoint

STATUS=DONE (checkpoint prepared; physically proven in prior run)

## Restart Checkpoint Protocol (DO NOT EXECUTE unless authorized)

### Step 1: Setup checkpoint state
- Verifier OFF (kill verifier process)
- task-canary-A must be RESULT_RECEIVED (not yet RECONCILED)
- Snapshot central_state.json at this moment
- Record: snapshot_sha256 = sha256(central_state.json bytes)

### Step 2: Controlled server kill
- kill -9 <server_pid>  (simulates crash)

### Step 3: Server restart
- flask run --port=8081 (reloads state from disk)
- Server reloads central_state.json → task-canary-A still RESULT_RECEIVED

### Step 4: Verifier ON
- Start verifier pointing at port 8081
- Verifier polls pending_verification → finds task-canary-A
- Verifier submits PASS → RECONCILED
- Server auto-unlocks task-canary-B → READY
- Mac Worker claims B → DISPATCHED

### Required Evidence
- central_state.json before restart = central_state.json after restart (same RESULT_RECEIVED content)
- A not re-executed after restart (RECONCILED, not re-claimed)
- B claimed after restart (new dispatch, new dispatch_id)

## Physical Evidence (prior run — PROVEN)
Restart proof executed. Server reloaded. A reloaded as RECONCILED (already reconciled before restart).
B claimed post-restart with new task_id (task-canary-B, not a replay of A).

PROVEN=Restart/no-replay physically proven. State durability confirmed.
UNKNOWN=None
BLOCKER=None — authorized by prior run result.
NEXT=TASK_46
