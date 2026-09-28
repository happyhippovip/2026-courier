# MAC-FINISH-13 — RUN_1 Operator Sheet

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-13
- **Area**: RUN1_OPERATOR_SHEET
- **Status**: COMPLETE

Comprehensive operator sheet detailing step-by-step physical execution of RUN_1.

---

## 2. Pre-Flight Verification Checklist
Assert all 10 invariants before starting:
1. `[ ]` `PORT=8081` free: `lsof -i :8081` returns empty.
2. `[ ]` `PORT=8080` untouched (production unharmed).
3. `[ ]` Clean directory `server/state/isolated_run1` prepared.
4. `[ ]` Lock `/tmp/courier_heavy_job.lock` acquired exclusively.
5. `[ ]` Memory > 1.0 GB available (`vm_stat`).
6. `[ ]` Pre-Codex cleared: `READY_FOR_PHYSICAL_RUN=YES`.
7. `[ ]` 44 targeted tests pass: `pytest` passes with 0 failures.
8. `[ ]` 12-case matrix passes.
9. `[ ]` Clean git tree: `git diff --check` passes.
10. `[ ]` Auth token `TEST_COURIER_AUTH_TOKEN_8081` configured.

---

## 3. Execution Commands
```bash
# 1. Boot Staging Server
PORT=8081 STATE_DIR=server/state/isolated_run1 python3 server/app.py > logs/run1_server.log 2>&1 &
SERVER_PID=$!
sleep 2

# 2. Run Autonomous End-to-End Canary Chain
python3 scripts/courier_verifier.py --port 8081 --canary-chain

# 3. Assert Results and Clean Shutdown
kill -TERM ${SERVER_PID}
wait ${SERVER_PID} 2>/dev/null
```
