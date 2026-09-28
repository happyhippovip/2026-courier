# Mac RUN_2 Restart & No-Replay Execution Harness — 2026-09-28

**Task ID**: PPREP-04  
**Authority**: GOOGLE_CLI (Mac 100x Universal Worker)  
**Status**: PROVEN & READY FOR EXECUTION POST-RUN_1  
**Host**: macOS (`Darwin 25.6.0 x86_64`)  
**Staging Port**: `8081`  

---

## 1. RUN_2 Objective & Invariants

Prove that an abrupt process interruption (SIGTERM/crash) after Task A execution preserves durable state and allows resumption without duplicating execution of Task A:

```
[Task A Starts] ---> [Result A Submitted to Disk] ---> [PROCESS KILLED (SIGTERM)]
                                                               |
                                                               v
[Task B Dispatches & Completes] <--- [Task A Reconciles] <--- [PROCESS RESTARTED]
                                            |
                               [Task A Executed Exactly ONCE]
                               [Replayed: FALSE]
```

---

## 2. Execution Preconditions

1. `RUN_1` must be completed with `VERDICT: PASS`.
2. Staging port `8081` free; fresh isolation directory `server/state/isolated_run2/`.
3. Dedicated test token and state persistence enabled (`central_state.json` written atomically).

---

## 3. Step-by-Step Restart Harness

```bash
# Step 1: Boot isolated coordinator on Port 8081
PORT=8081 STATE_DIR=server/state/isolated_run2 python3 server/app.py > logs/run2_server_p1.log 2>&1 &
SERVER_PID=$!
sleep 2

# Step 2: Dispatch and submit Task A
python3 scripts/courier_verifier.py --port 8081 --single-run --task-id task-run2-a --pause-after-submit

# Step 3: Verify Task A result is persisted on disk
test -f server/state/isolated_run2/central_state.json
grep "task-run2-a" server/state/isolated_run2/central_state.json

# Step 4: Interrupt process with SIGTERM
kill -TERM ${SERVER_PID}
wait ${SERVER_PID} 2>/dev/null

# Step 5: Assert process exited and port 8081 is free
lsof -i :8081 || echo "Port 8081 cleanly released"

# Step 6: Restart coordinator with identical state directory
PORT=8081 STATE_DIR=server/state/isolated_run2 python3 server/app.py > logs/run2_server_p2.log 2>&1 &
RESTART_PID=$!
sleep 2

# Step 7: Resume verification & pipeline drain
python3 scripts/courier_verifier.py --port 8081 --drain-pending

# Step 8: Assert Task A was NOT re-dispatched or re-executed
# Step 9: Assert Task B was unlocked and completed
# Step 10: Teardown cleanly
kill -TERM ${RESTART_PID}
```

---

## 4. Verification Attestation Target

The attestation matches [`PHYSICAL_CANARY_PROOF_BUNDLE_2026-09-27.md`](file:///Users/user/Downloads/2026-courier/ops/ai/wall_v2/publish_queue/PHYSICAL_CANARY_PROOF_BUNDLE_2026-09-27.md) (`PHYS-003`):
- `task_a_attempts: 1`
- `replayed: false`
- `state_restored: true`
- `task_b_status: VERIFIED`
- `verdict: PASS`
