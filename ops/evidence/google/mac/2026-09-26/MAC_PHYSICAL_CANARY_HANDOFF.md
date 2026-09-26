# MAC_PHYSICAL_CANARY_HANDOFF

HOST=MAC
ROLE=PHYSICAL_CANARY_PREPARATION_OWNER
DATE=2026-09-26

LOCAL_BRANCH=agent/canonical-wall-supervisor-v2
LOCAL_SHA=332a42f9edcf1de1535870592da34a7961880991

CANDIDATE_AVAILABLE=YES (Available on origin/candidate-b-1)
CANDIDATE_SHA=4c1e24ccc522042af826bc4c2b595daf85d097f9

REAL_MUSE_BINARY=/Users/user/.local/bin/muse
REAL_MUSE_VERSION=Muse Code 1.4.0 (1.4.0-R4161.1)

SERVER_STATE=ACTIVE (Production PID 69407 on port 8080 completely undisturbed; Canary ran hermetically on port 8081)
VERIFIER_STATE=ACTIVE (Production PID 42002 on port 8080 completely undisturbed; Canary verifier executed hermetically)
DAEMON_STATE=ACTIVE (Production PID 46250 completely undisturbed)

LIVE_RUNTIME_AUTHORITY=REST API bound to central_state.json

SAFE_CANARY_WORKSPACE=/Users/user/Downloads/courier_canary
SAFE_CANARY_PORT=8081 (Verified 100% collision-free)

PHYSICAL_PROOF_SUMMARY:
- AUFTRAG=goal-canary-01
- A_ERLEDIGT=YES
- A_GEPRUEFT=YES (VERIFIER-01 independent verification of server-stored artifact bytes)
- B_AUTOMATISCH_GESTARTET=YES (Step index advanced from 0 to 1 without human intervention)
- B_ERLEDIGT=YES
- A_EXECUTION_COUNT=1
- HUMAN_RELAY_COUNT=0
- DETERMINISTIC_RESTART_NO_REPLAY=PROVEN (Server SIGKILL, restart, state reloaded intact, zero replay of Task A)
- BEWEIS=HERMETIC_PHYSICAL_RUN_PORT_8081_CANDIDATE_B_1

READY_FOR_BOUND_CANDIDATE=YES
PHYSICAL_CANARY_COMPLETED=YES
