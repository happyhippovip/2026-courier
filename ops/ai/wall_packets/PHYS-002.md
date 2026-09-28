# Physical Proof Packet: PHYS-002 — RUN_1 Canary Pass

TASK_ID=PHYS-002
PRIORITY=P0
DEPENDENCIES=PHYS-001
EXACT_INPUTS=scripts/mac_worker/muse_supervisor.py
EXACT_FILES_OR_RESULTS=COURIER_SERVER=http://127.0.0.1:8081
ALLOWED_ACTION=PHYSICAL_PROOF
DONE_CONDITION=Task A executes -> Verifier confirms exact SHA -> Task B auto-dispatches; zero human relay
EXPECTED_OUTPUT=Proof bundle JSON with human_relay_count=0 and verdict=PASS
DO_NOT_REPEAT_FINGERPRINT=phys-run1-canary-002
