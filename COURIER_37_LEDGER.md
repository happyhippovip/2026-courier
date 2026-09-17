# Courier #37 Ledger / Checkpoint

| Key | Value |
| --- | --- |
| CURRENT_SHA | b6b46534c78ee4b4f2699712d9473b9835b7e906 |
| CENTRAL_BRANCH_SHA | b6b46534c78ee4b4f2699712d9473b9835b7e906 |
| LEDGER_REVISION | 6 |
| RUNTIME_OWNER | WINDOWS/CENTRAL |
| CENTRAL_ENDPOINT | http://192.168.178.87:8080 |
| OS_OWNED_PERSISTENT_MOTOR | UNKNOWN (Cannot verify from Mac) |
| GOALS_SUBMITTED | UNKNOWN |
| TASKS_COMPLETED | UNKNOWN |
| WORKERS_USED | UNKNOWN |
| USER_CONTINUE_MESSAGES | UNKNOWN |
| MANUAL_PROCESS_RESTARTS | UNKNOWN |
| MANUAL_ACCOUNT_CONTEXT_RECONSTRUCTION | UNKNOWN |
| DUPLICATE_EXTERNAL_EFFECTS | UNKNOWN |
| TEMP_TASK_PROCESSES_AFTER_DONE | UNKNOWN |
| WAITING_PROVIDER_PROVEN | UNKNOWN |
| RESTART_RESUME_PROVEN | UNKNOWN |
| AUTO_REPLENISH_PROVEN | UNKNOWN |
| CLEAN_IDLE | UNKNOWN |
| QUEUE_INDEPENDENT | UNKNOWN |
| PHYSICAL_ACCEPTANCE_PASS | UNKNOWN |
| FIRST_CAUSAL_BLOCKER | HUMAN_REQUIRED_WINDOWS_CENTRAL_AUTHORITY |
| NEXT_EXECUTABLE_ACTION | NONE |
| WORKER_STATE | IDLE/YIELDED |
| AUTO_DISPATCH_INVARIANT_PROVEN | YES (fc48f83d) |
| OWNED_BACKGROUND_TASKS_TRACKED | YES |
| OWNED_BACKGROUND_TASKS_AFTER_HANDOFF | 0 |
| UNRELATED_PROCESSES_KILLED | 0 |
| COURIER_OS_MOTOR_UNTOUCHED | YES |

## Proof Run Output
```text
================ REAL WINDOWS CENTRAL + MULTI-WORKER E2E PROOF ================
Target Canonical Server: http://192.168.178.87:8080
[Central] Detected running Central server with 0 registered workers.

[Step 1/5] Checking launchd-owned Mac Worker registration...
  [PASS] Found active launchd Mac worker: MAC-MACBOOK-PRO-VON-USER-EDEA96

[Step 2/5] Starting second real worker MAC-CLI-1...
  [PASS] MAC-CLI-1 registered successfully!
  [CONFIRMED] Both real workers active in Central: MAC-MACBOOK-PRO-VON-USER-EDEA96 and MAC-CLI-1

[Step 3/5] Submitting 10-Task DAG Goal...
  [PASS] Goal goal-5cfaddca submitted to Central Motor.

[Step 4/5] Observing zero-touch execution across both real workers...
  [PASS] All 10 tasks reached RECONCILED and Goal reached DONE in 20.3s!

[Step 5/5] Auditing Physical Acceptance Evidence...
  Goal Status: DONE
  Tasks Reconciled: 10/10
  Participating Workers: {'MAC-MACBOOK-PRO-VON-USER-EDEA96', 'MAC-CLI-1'}

================ ACCEPTANCE EVIDENCE SUMMARY ================
WINDOWS_CENTRAL_USED:        YES (192.168.178.87:8080)
LAUNCHD_WORKER_PARTICIPATED: YES
CLI_WORKER_PARTICIPATED:     YES
WORKERS_USED:                2
TASKS_COMPLETED:             10
ALL_ARTIFACTS_ON_DISK:       YES
CANONICAL_GOAL_DONE:         YES
-------------------------------------------------------------
PHYSICAL_ACCEPTANCE_PASS:    YES
QUEUE_INDEPENDENT:           YES
=============================================================
```
