# MAC02 Process Ownership Preflight — Mac/Courier

Slot: MAC02_PROCESS (unique C2 claim, runtime/process isolation).
Host: Mac, repo `/Users/user/Downloads/2026-courier`, HEAD `bd539f18`.
No process was signaled or killed (prep only).

## Ownership map (observed, read-only)

- Foreign, protected: PID 606 (PPID 1, PGID 606, `python -m server.app`) LISTEN on :8080. Never signal.
- Foreign, protected: PID 629 (`scripts/courier_verifier.py`), PID 620 (`scripts/mac_worker/daemon.py`). Never signal.
- Staging :8081: free (`lsof -i :8081` exit 1). Boot precondition holds.
- Own shell PGID distinct from 606 (verified via `ps -o pid,ppid,pgid`). Only own PGID is signalable.
- Peer claim `ops/ai/wall_claims/MUSE_HNI_06_TWELVE_CASE_MATRIX_QA.claim.json` is foreign — untouched.

## Rules bound for RUN_1/RUN_2

1. Pre-flight abort if :8081 occupied or `pgrep -f "run_physical.py --sha <FINAL>"` hits (per `scripts/run1_physical/PROCESS_PORT_OWNERSHIP.md`).
2. TERM/KILL only own PGID (`kill -TERM -<own_pgid>`); never bare-PID kill from a pidfile value.
3. Orphan detection: `logs/courier_daemon.pid` = 46397, no live PID (orphan *record*, not a process). Record only; no action on PID reuse risk.
4. `state/wall/supervisor.lock` (0 B, 26 Sep): treat as stale-suspect; verify holder before any boot, never delete blindly.
5. Timeouts: boot liveness `sleep 2` + curl per RUN_1 checklist; kill→verify-port-free→restart sequence per RUN_2 harness. No tight loops in harness itself.

## Result block

TASK_ID=MAC02_PROCESS
FAMILY=runtime/process-isolation
STATUS=PREP_DONE (no execution, zero signals sent)
RESULTS_REUSED=PROCESS_PORT_OWNERSHIP.md + STATE_LOG_ARTIFACT_ISOLATION.md (read, not duplicated)
FINDING=none blocking ownership; :8081 free, foreign PIDs mapped and protected
MISSING_EVIDENCE=RUN-time PGID of staging server (exists only at boot)
NEXT_EXACT_ACTION=keep MAC03/MAC08 green; boot RUN_1 only after resource gate passes + writer clearance
DO_NOT_REPEAT_FINGERPRINT=MAC02-pgid-map-20260928-bd539f18
