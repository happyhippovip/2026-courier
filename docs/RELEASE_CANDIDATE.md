# RELEASE CANDIDATE
VERSION=1.0.0-rc.1
SCHEMA_VERSION=v4
OS_SUPPORT=Windows (Primary), Mac (Not Run - Supported), Linux (Not Run - Supported)

SELLABLE_RELEASE_CANDIDATE=YES
GOAL_ONLY_MODE=YES
CORE_ENGINEERING_QUEUE_EMPTY=YES

## CURRENT EXECUTION CHECKPOINT

PLANNING_PHASE=FROZEN
FIRST_CURRENT_CAUSAL_BLOCKER=NONE_PROVEN
NEXT_ACTION=RUN_PHYSICAL_ACCEPTANCE_PROOF
PHYSICAL_ACCEPTANCE_TARGET=CURRENT_PR_HEAD_AT_RUN_START
NO_NEW_ARCHITECTURE=YES
NO_SPEC_EXPANSION=YES
NO_PREEMPTIVE_REFACTOR=YES

### Motor ownership classification

SERVER_OS_START_PATH=OBSERVED_IN_CODE
VERIFIER_OS_START_PATH=OBSERVED_IN_CODE
MOTOR_OS_START_PATH=UNKNOWN_FROM_CURRENT_EVIDENCE

`UNKNOWN` MUST NOT be treated as `BROKEN`.

The physical proof must distinguish these possibilities from observed runtime behavior:

- A: Motor/dispatch/reconcile/READY-recompute logic is embedded in the OS-owned server/runtime and therefore inherits its lifecycle.
- B: Motor requires a separate persistent owner and no such owner is actually running.

Do not choose A or B from architecture assumptions. Observe real process/thread ownership and automatic transitions first.

### Required next proof

Against the exact current PR head at proof start:

1. Identify the real owners of server, verifier, and Motor behavior.
2. Confirm the relevant runtime is OS-owned and independent of the interactive terminal/agent.
3. Exit the interactive terminal/agent and prove the runtime continues.
4. Submit exactly one real non-mock Goal through the live API.
5. Use real workers, not an acceptance harness impersonating workers.
6. Observe automatic result -> verifier -> reconcile -> READY -> next dispatch/replenish.
7. Continue to >=10 acceptance-eligible completed tasks with >=2 real workers.
8. Require USER_CONTINUE_MESSAGES=0, MANUAL_PROCESS_RESTARTS=0, DUPLICATE_EXTERNAL_EFFECTS=0, TEMP_TASK_PROCESSES_AFTER_DONE=0, and genuine DONE -> CLEAN_IDLE.
9. The FIRST observed real break becomes the FIRST CAUSAL BLOCKER.
10. Only then make the smallest repair and rerun the SAME proof.

No new architecture, rule, agent, roadmap, or refactor is justified before a concrete current failure is observed.

### FIX: WINDOWS WRAPPER REMOVAL & POWERSHELL ENCODING
- Removed redundant windows polling wrappers (`start.bat`, `start.py`, `stop.bat`, etc.).
- Fixed PowerShell encoding bug in `daemon.py` by streaming instructions via stdin.
- Verified test `test_windows_runtime_torture.py` passes safely.
- New Checkpoint SHA (Fingerprint): f2def98d3c13cad67925983d7374be14d38ec4c8
