# MAC_PHYSICAL_CANARY_HANDOFF

**Generated:** 2026-09-26T17:28:00+02:00
**Host:** MAC (Darwin x86_64, MacBook-Pro-von-user.local)
**Role:** PHYSICAL_CANARY_PREPARATION_OWNER

---

LOCAL_BRANCH=agent/canonical-wall-supervisor-v2
LOCAL_SHA=332a42f9edcf1de1535870592da34a7961880991

CANDIDATE_AVAILABLE=YES
CANDIDATE_SHA=4c1e24ccc522042af826bc4c2b595daf85d097f9 (origin/candidate-b-1)

REAL_MUSE_BINARY=/Users/user/.local/bin/muse
REAL_MUSE_VERSION=Muse Code 1.4.0 (1.4.0-R4161.1)
MUSE_ADAPTER_MATCH=MISMATCH (Physical CLI rejects '--reasoning-effort auto'; requires 'high' or omission)

SERVER_STATE=RUNNING (PID 69407 on port 8080)
VERIFIER_STATE=RUNNING (PID 42002 polling /tasks/pending_verification)
SUPERVISOR_STATE=IDLE (No active supervisor process)
DAEMON_STATE=RUNNING (PID 46250 polling /tasks/claim)

LIVE_RUNTIME_AUTHORITY=Server PID 69407 / Verifier PID 42002 / Worker PID 46250

SAFE_CANARY_WORKSPACE=/Users/user/Downloads/courier_work/canary_isolated_workspace
SAFE_CANARY_PORT=8085 (or existing 8080)
ARTIFACT_PATH=.courier_artifacts/ (blobs/ and records/)
STATE_PATH=server/state/central_state.json
LOG_PATHS=logs/courier_server.log, scripts/mac_worker/logs/launchd.log

RESOURCE_BASELINE=CPU: 46% user / 42% idle; MEMORY: 8.2GB occupied / 910MB free; SWAP: 1.2GB free; ACTIVE_MUSE: 34; ACTIVE_COURIER: 3

BLOCKERS=NONE (Windows Candidate B contains required server/verifier patches; Muse CLI flag fix documented)
UNKNOWN=NONE

READY_FOR_BOUND_CANDIDATE=YES
READY_FOR_PHYSICAL_CANARY=YES
