# MAC-FINISH-15 — RUN_2 Restart Operator Sheet

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-15
- **Area**: RUN2_RESTART_OPERATOR_SHEET
- **Status**: COMPLETE

Step-by-step physical execution protocol for RUN_2 crash and restart validation.

---

## 2. Preconditions
- Prerequisite: `RUN_1` completed with `VERDICT: PASS`.
- Port 8081 verified free.
- Fresh isolation directory `server/state/isolated_run2`.

---

## 3. Step-by-Step Operator Runbook
```bash
# Step 1: Boot Phase 1 Coordinator
PORT=8081 STATE_DIR=server/state/isolated_run2 python3 server/app.py > logs/run2_server_p1.log 2>&1 &
SERVER_PID=$!
sleep 2

# Step 2: Execute Task A only
python3 scripts/courier_verifier.py --port 8081 --single-run --task-id task-run2-a --pause-after-submit

# Step 3: Inject Crash (SIGTERM)
kill -TERM ${SERVER_PID}
wait ${SERVER_PID} 2>/dev/null

# Step 4: Assert Clean Exit and Port Release
lsof -i :8081 || echo "Port 8081 successfully released"

# Step 5: Boot Phase 2 Coordinator (Same STATE_DIR)
PORT=8081 STATE_DIR=server/state/isolated_run2 python3 server/app.py > logs/run2_server_p2.log 2>&1 &
RESTART_PID=$!
sleep 2

# Step 6: Assert Resumption Without Replaying Task A
python3 scripts/courier_verifier.py --port 8081 --assert-no-replay --task-id task-run2-a

# Step 7: Clean Shutdown
kill -TERM ${RESTART_PID}
wait ${RESTART_PID} 2>/dev/null
```
