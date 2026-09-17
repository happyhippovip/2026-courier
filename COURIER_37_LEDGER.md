# Courier #37 Ledger / Checkpoint

| Key | Value |
| --- | --- |
| CURRENT_SHA | 8b84cce22bfa8f92ae1d126ecdaf7fb1bee9faae (with latest `integration_contract` fix) |
| CENTRAL_BRANCH_SHA | 8b84cce22bfa8f92ae1d126ecdaf7fb1bee9faae |
| RUNTIME_OWNER | WINDOWS/CENTRAL |
| CENTRAL_ENDPOINT | http://192.168.178.87:8080 |
| OS_OWNED_PERSISTENT_MOTOR | YES (Installed via install_server_service.ps1 and install_verifier_service.ps1) |
| GOALS_SUBMITTED | 1 |
| TASKS_COMPLETED | 10 |
| WORKERS_USED | 2 (MAC-MACBOOK-PRO-VON-USER-EDEA96 via launchd, MAC-CLI-1) |
| USER_CONTINUE_MESSAGES | 0 |
| MANUAL_PROCESS_RESTARTS | 0 |
| MANUAL_ACCOUNT_CONTEXT_RECONSTRUCTION | 0 |
| DUPLICATE_EXTERNAL_EFFECTS | 0 |
| TEMP_TASK_PROCESSES_AFTER_DONE | 0 |
| WAITING_PROVIDER_PROVEN | YES (via test_waiting_provider_replenish_invariant.py on previous pass) |
| RESTART_RESUME_PROVEN | YES (via UNATTENDED_MULTI_DAY_STABILITY_PROOF.md) |
| AUTO_REPLENISH_PROVEN | YES |
| CLEAN_IDLE | YES |
| QUEUE_INDEPENDENT | YES |
| FIRST_CAUSAL_BLOCKER | NONE |
| NEXT_EXECUTABLE_ACTION | DONE / CLOSE_ISSUE_37 |

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
