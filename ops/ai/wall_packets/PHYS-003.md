# Physical Proof Packet: PHYS-003 — RUN_2 Restart Persistence & Replay Gate

TASK_ID=PHYS-003
PRIORITY=P0
DEPENDENCIES=PHYS-002
EXACT_INPUTS=scripts/mac_worker/muse_supervisor.py, server/app.py
EXACT_FILES_OR_RESULTS=PORT=8081, COURIER_STATE_DIR=/Users/user/courier_work/canary_run1/state
ALLOWED_ACTION=PHYSICAL_PROOF
DONE_CONDITION=Graceful restart of staging coordinator preserves state; Task A is NOT replayed (attempts == 1); Task B reconciles cleanly
EXPECTED_OUTPUT=Proof record documenting restart persistence, zero Task A replay, and clean reconciliation
DO_NOT_REPEAT_FINGERPRINT=phys-run2-restart-gate-003
