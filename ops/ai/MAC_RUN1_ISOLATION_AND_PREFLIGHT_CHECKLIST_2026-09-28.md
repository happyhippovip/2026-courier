# Mac RUN_1 Isolation & Preflight Checklist — 2026-09-28

**Task ID**: PPREP-02  
**Authority**: GOOGLE_CLI (Mac 100x Universal Worker)  
**Status**: PROVEN & READY FOR RUN_1 EXECUTION  
**Host**: macOS (`Darwin 25.6.0 x86_64`)  
**Staging Port**: `8081` (Strictly isolated from Production Port `8080`)  

---

## 1. RUN_1 Objective & Contract

Prove physical zero-human execution of the end-to-end task chain:

```
[GOAL] ---> [Task A Dispatched] ---> [Worker A Executes] ---> [Result A Submitted]
                                                                    |
                                                                    v
[Task B Dispatched] <--- [Task B Legal] <--- [Task A Reconciled] <--- [Server Verifies Hash]
       |
       v
[Worker B Executes] ---> [Result B Submitted] ---> [Server Verifies Hash] ---> [Goal Complete]
                                                                                       |
                                                                   [HUMAN_RELAY_COUNT=0]
```

---

## 2. Preflight Isolation Invariants

Before launching the physical RUN_1 process, assert the following 10 boolean checks:

| # | Check Item | Verification Command / Method | Required Outcome |
|---|---|---|---|
| 1 | **Port 8081 Free** | `lsof -i :8081` | No active process listening |
| 2 | **Port 8080 Untouched** | `lsof -i :8080` (if production) | Staging run must not bind or interfere |
| 3 | **State Isolation** | Check directory `server/state/isolated_run1` | Fresh, clean, empty before boot |
| 4 | **Artifacts Sandboxing** | Check `server/state/isolated_run1/artifacts` | Isolated directory, no collision |
| 5 | **Coordinator Authorization** | Auth token `TEST_COURIER_AUTH_TOKEN_8081` | Distinct staging bearer token |
| 6 | **Heavy Job Concurrency** | Check `/tmp/courier_heavy_job.lock` | Acquired exclusively (`MAX_HEAVY_JOBS=1`) |
| 7 | **Memory Availability** | `vm_stat` / physical memory check | > 1.0 GB available memory |
| 8 | **Pre-Codex Clearance** | Check `GOOGLE_PRE_CODEX_GATE_2026-09-27.md` | `READY_FOR_PHYSICAL_RUN=YES` |
| 9 | **Test Execution Pre-Pass** | Run 44 targeted tests against `FINAL_SHA` | 44 PASS, `SKIPPED=0` |
| 10 | **Git Tree Cleanliness** | `git diff --check` | 0 whitespace or formatting errors |

---

## 3. Physical RUN_1 Execution Sequence

When cleared by `READY_FOR_PHYSICAL_RUN=YES`:

```bash
# 1. Acquire heavy lock
touch /tmp/courier_heavy_job.lock

# 2. Boot isolated staging server on Port 8081
PORT=8081 STATE_DIR=server/state/isolated_run1 python3 server/app.py > logs/run1_server.log 2>&1 &
SERVER_PID=$!
sleep 2

# 3. Verify server liveness
curl -s http://127.0.0.1:8081/health | grep '"status":"ok"'

# 4. Dispatch Task A and launch worker
python3 scripts/courier_verifier.py --port 8081 --single-run --task-id task-run1-a

# 5. Assert Task A verification & reconcile in state DB
# 6. Assert Task B auto-unlocks and executes
python3 scripts/courier_verifier.py --port 8081 --single-run --task-id task-run1-b

# 7. Teardown & collect attestation
kill -TERM ${SERVER_PID}
rm -f /tmp/courier_heavy_job.lock
```

---

## 4. Attestation Verification Target

The resulting physical attestation bundle must match [`PHYSICAL_CANARY_PROOF_BUNDLE_2026-09-27.md`](file:///Users/user/Downloads/2026-courier/ops/ai/wall_v2/publish_queue/PHYSICAL_CANARY_PROOF_BUNDLE_2026-09-27.md) (`PHYS-002`), asserting:
- `task_a_status: VERIFIED`
- `task_b_status: VERIFIED`
- `human_relay_count: 0`
- `failures_encountered: 0`
- `verdict: PASS`
