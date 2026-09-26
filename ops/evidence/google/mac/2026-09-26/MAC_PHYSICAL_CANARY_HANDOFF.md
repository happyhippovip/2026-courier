# MAC_PHYSICAL_CANARY_HANDOFF

LOCAL_BRANCH=agent/canonical-wall-supervisor-v2
LOCAL_SHA=332a42f9edcf1de1535870592da34a7961880991

CANDIDATE_AVAILABLE=YES (Available on origin/candidate-b-1 at 4c1e24cc; includes server idempotency, artifact store, and expected_sha256 verification)
CANDIDATE_SHA=4c1e24ccc522042af826bc4c2b595daf85d097f9

REAL_MUSE_BINARY=/Users/user/.local/bin/muse
REAL_MUSE_VERSION=Muse Code 1.4.0 (1.4.0-R4161.1)
MUSE_ADAPTER_MATCH=FAIL (scripts/muse_wall_supervisor.py passes invalid --reasoning-effort auto and un-namespaced resume session ID)

SERVER_STATE=ACTIVE (PID 69407 on port 8080, RSS 10.2 MB, CPU 0.0%)
VERIFIER_STATE=ACTIVE (PID 42002 on port 8080)
SUPERVISOR_STATE=IDLE (0 running supervisor processes)
DAEMON_STATE=ACTIVE (PID 46250)

LIVE_RUNTIME_AUTHORITY=REST API on port 8080 bound to server/state/central_state.json

SAFE_CANARY_WORKSPACE=/Users/user/Downloads/courier_canary
SAFE_CANARY_PORT=8081 (Verified 100% free; port 8080 reserved for production server)
ARTIFACT_PATH=/Users/user/Downloads/courier_canary/artifacts
STATE_PATH=/Users/user/Downloads/courier_canary/server/state/central_state.json
LOG_PATHS=/Users/user/Downloads/2026-courier/logs/courier_server.log, /Users/user/.courier_runtime/logs/courier_verifier.log, /Users/user/Downloads/2026-courier/scripts/mac_worker/logs/launchd.log

RESOURCE_BASELINE=CPU load 10.13, 9.85, 13.24; PhysMem 14 GB used, 1.58 GB unused; 34 background Muse processes; 15 Courier processes. Control plane consumes 10.2 MB RSS and 0.0% CPU.

BLOCKERS=M45-MUSE-CLI-REASONING-EFFORT-01 (Flag --reasoning-effort auto crashes muse exec with exit code 2; requires Windows single-writer to patch scripts/muse_wall_supervisor.py)
UNKNOWN=NONE (All physical dimensions directly measured on hardware)

READY_FOR_BOUND_CANDIDATE=YES
READY_FOR_PHYSICAL_CANARY=GATED_ON_WRITER_CLI_PATCH
