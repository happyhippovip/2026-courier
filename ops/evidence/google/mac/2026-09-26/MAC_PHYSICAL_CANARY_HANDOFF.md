# MAC_PHYSICAL_CANARY_HANDOFF.md
# MISSION=COURIER_GOOGLE_DUAL_HOST_QUEUE_50
# DATE=2026-09-26  UPDATED=20:16 CET

LOCAL_BRANCH=agent/canonical-wall-supervisor-v2
LOCAL_SHA=332a42f9edcf1de1535870592da34a7961880991

CANDIDATE_AVAILABLE=YES
CANDIDATE_BRANCH=origin/candidate-b-1
CANDIDATE_SHA=4c1e24ccc522042af826bc4c2b595daf85d097f9
CANDIDATE_BASE_SHA=3e2fe24d6dc59d7613aec9d1099695f5520c4733
CANDIDATE_AUTHOR=Google Windows <google-windows@local.internal>
CANDIDATE_DATE=2026-09-26T17:19:41+0200
CANDIDATE_COMMITS=4 (4c1e24cc, 7b993162, 8173f17e, 8d2384df)

REAL_MUSE_BINARY=/Users/user/.local/bin/muse
REAL_MUSE_VERSION=Muse Code 1.4.0 (1.4.0-R4161.1)
MUSE_ADAPTER_MATCH=PARTIAL
  MATCH=exec subcommand, --workspace, --yolo
  MISMATCH=reasoning_effort="auto" in muse_wall_supervisor.py:39 (BUG M45-MUSE-CLI-ARG-01)
  FIX_IN_CANDIDATE=NO — muse_wall_supervisor.py not changed in candidate-b-1

SERVER_STATE=RUNNING (PID 69407, port 8080, source 332a42f9)
VERIFIER_STATE=RUNNING (PID 42002)
SUPERVISOR_STATE=NOT_RUNNING (blocked by reasoning_effort bug)
DAEMON_STATE=RUNNING (PID 46250, mac_worker/daemon.py)

LIVE_RUNTIME_AUTHORITY=PID 69407 server @ port 8080

SAFE_CANARY_WORKSPACE=/Users/user/Downloads/courier_canary/  (prior proof run complete)
SAFE_CANARY_PORT=8081  (confirmed free)
ARTIFACT_PATH=/Users/user/Downloads/courier_canary/artifacts/
  canary_A.txt: COURIER-A2B-A\n (12 bytes, sha256=96c1471cc2dfc55d49de5a3279dc927774a84b0f5c5bdc7c5755f19d8de9391c)
STATE_PATH=/Users/user/Downloads/courier_canary/server/state/central_state.json
  task-canary-A: RECONCILED
  task-canary-B: DISPATCHED
LOG_PATHS=
  /Users/user/Downloads/2026-courier/scripts/mac_worker/logs/worker.log
  /Users/user/Downloads/2026-courier/logs/courier_motor.log

RESOURCE_BASELINE=
  RAM_TOTAL=16GB
  RAM_FREE=~2.1GB (pages_free * 4096)
  DISK_FREE=602GB (/Users/user/Downloads)
  CPU_LOGICAL=16
  SERVER_RSS=9.4MB (PID 69407)
  VERIFIER_RSS=9.5MB (PID 42002)
  WORKER_RSS=7.2MB (PID 46250)

BLOCKERS=
  1. muse_wall_supervisor.py:39 reasoning_effort="auto" → exit 2 (supervisor path only)
  2. candidate-b-1 not yet deployed to courier_canary workspace
  BLOCKING_CANARY_WITH_SUPERVISOR=YES
  BLOCKING_CANARY_WITH_DIRECT_EXEC=NO (direct muse exec --reasoning-effort high works)

UNKNOWN=
  1. Whether Windows will commit supervisor fix in follow-up
  2. Whether candidate-b-1 artifact_store path works E2E with canary server (not yet physically run)

READY_FOR_BOUND_CANDIDATE=YES
  candidate-b-1 @ 4c1e24cc fetched, source-audited, authorized scope confirmed

READY_FOR_PHYSICAL_CANARY=YES
  Option A: Deploy candidate-b-1 to courier_canary_b1/ workspace, run A→VERIFY→B with artifact upload
  Option B: Wait for supervisor fix, then run full supervisor-mediated Canary
  Prior proof run already validates base flow (A→VERIFY→B RECONCILED, restart no-replay proven)

## Key Authorized Changes in candidate-b-1
- scripts/artifact_store.py (NEW): Server-owned artifact store, content-addressed blobs, idempotent uploads
- server/app.py (MODIFIED): Imports artifact_store, registers ARTIFACT_STORE, checks artifact references
- scripts/courier_verifier.py (MODIFIED): Fetches artifacts from server, expected_sha256 check against server bytes
- scripts/windows_worker/daemon.py (MODIFIED): PowerShell encoding + locking fixes (Windows-only)

## Physical Evidence Already Collected
- /Users/user/Downloads/courier_work/google_longrun/reports/GOOGLE_CLI_A_VERIFY_B_RUNTIME_EVIDENCE.json
- /Users/user/Downloads/courier_work/google_longrun/reports/GOOGLE_CLI_RESTART_REPLAY_EVIDENCE.md
- /Users/user/Downloads/courier_work/google_longrun/reports/GOOGLE_CLI_PHYSICAL_RUNTIME_AND_BINDING_CARD.md
- /Users/user/Downloads/courier_work/google_longrun/reports/CLI5_VISIBLE_PROOF.md

## UPDATE 17:44 — New Physical Facts (GOOGLE_CLI_MAC_PHYSICAL_FACT_QUEUE.md)
MUSE_DEFECT_2=M45-MUSE-SESSION-ID-MISSING-01: exec_task() missing --session-id; resume/session-message broken
MUSE_DEFECT_3=M45-SESSION-MESSAGE-FORMAT-01: muse session-message send --target <UUID> <MSG> (not current adapter format)
VERIFIER_CWD=PID 42002 CWD=/Users/user/.courier_runtime (must run canary verifier from courier_canary/ root)
MEMORY_PRESSURE=CRITICAL: swap 13.54GB/14GB used, 35 muse processes active → defer canary to low-load window
PHYSICAL_PREFLIGHT=PASS (Courier processes healthy, port 8081 free, workspace isolated)
ADDITIONAL_BLOCKERS=
  M45-VERIFIER-CWD-ANCHOR-01 (canary verifier CWD must be courier_canary/)
  M45-MUSE-SESSION-ID-MISSING-01 (for resume path; not on critical path for simple Canary 1)
  M45-SESSION-MESSAGE-FORMAT-01 (for session messages; not on critical path for Canary 1)
SAFE_FOR_SIMPLE_CANARY_1=YES (direct muse exec + manual artifact write, no supervisor/resume needed)

## UPDATE 20:16 CET — MISSION=MAC_FINAL_PHYSICAL_RUNNER

### Muse stdout contract PHYSICALLY PROVEN (20:15 CET)
MUSE_STDOUT_CONTRACT=RESOLVED
COMMAND_TESTED=muse exec --workspace /Users/user/Downloads/courier_work/muse_stdout_probe/scratch_ws --yolo 'Output exactly: {"status":"SUCCESS","summary":"probe"}'
STDOUT_OUTPUT={"status":"SUCCESS","summary":"probe"}
EXIT_CODE=0
STDERR_ONLY_PREFIX_LINES=YES (muse: workspace root: ..., muse: workspace trust: ...)
PHYSICAL_EVIDENCE=task-1305 log, 20:14-20:15 CET
BLOCKER_CLOSED=MUSE_STDOUT_CONTRACT

### Final Candidate Status
FINAL_CANDIDATE_REQUIRED=candidate-b-3 (Windows building — NOT YET PUSHED)
CANDIDATE_B1=4c1e24ccc522042af826bc4c2b595daf85d097f9 (authorized base, present on origin)
CANDIDATE_B2=83940de3d7d33776a712e7506aa76726d16f8587 (REJECTED, present on origin)
CANDIDATE_B3=WAITING (Windows MISSION=BUILD_FINAL_CANONICAL_CANDIDATE_B3 in progress)

### Canary B fixtures
CANARY_A_CONTENT=COURIER-A2B-A\n (12 bytes)
CANARY_A_SHA256=96c1471cc2dfc55d49de5a3279dc927774a84b0f5c5bdc7c5755f19d8de9391c
CANARY_B_CONTENT=COURIER-A2B-B\n (14 bytes)
CANARY_B_SHA256=b9032958fc90e7380195fcc51eca5822d60bb31eb15d370a44c3c15e60942a50

### RUN_1 Isolation
RUN1_WORKSPACE=/Users/user/Downloads/courier_work/canary_run1/
RUN1_PORT=8081 (confirmed free)
RUN1_STATE=PREP_COMPLETE — waiting for final SHA before binding

### Current Blockers
BLOCKER_1=candidate-b-3 SHA not yet available (Windows building)
BLOCKER_2=None — Muse stdout resolved, isolation ready, fixtures confirmed
NEXT_ACTION=On candidate-b-3 push: fetch, deploy to canary_run1/, bind server, run RUN_1
