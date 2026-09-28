# Physical Proof Packet: PHYS-001 — Staging Server Binding & Isolation

TASK_ID=PHYS-001
PRIORITY=P0
DEPENDENCIES=NONE
EXACT_INPUTS=scripts/mac_worker/muse_supervisor.py, server/app.py
EXACT_FILES_OR_RESULTS=PORT=8081, COURIER_STATE_DIR=/Users/user/courier_work/canary_run1/state
ALLOWED_ACTION=TARGETED_TEST
DONE_CONDITION=Staging server responsive on http://127.0.0.1:8081/health with HTTP 200
EXPECTED_OUTPUT=Receipt with server PID, bound port, and clean status
DO_NOT_REPEAT_FINGERPRINT=phys-staging-bind-001
