# Result for PHYS-003
- **TASK_ID**: PHYS-003
- **STATUS**: PASS
- **VERDICT**: PASS
- **INPUTS_READ**: scripts/mac_worker/muse_supervisor.py, server/app.py, /Users/user/courier_work/canary_run1/run2_restart_gate.py
- **FINDING**: RUN_2 Controlled Restart Persistence & Replay Gate verified end-to-end. Prior RUN_1 state survived coordinator restart with attempts=1. In RUN_2, Task A executed and verified to RECONCILED. Coordinator was stopped with SIGTERM and restarted with a new PID (PID 15728). Post-restart assertions confirmed Task A retained RECONCILED status with attempts=1, zero replay occurred, and the next claim automatically dispatched Task B (attempts=1). Task B completed and verified to RECONCILED. Proof bundle JSON persisted at /Users/user/courier_work/canary_run1/run2_proof.json.
- **DO_NOT_REPEAT**: phys-run2-restart-gate-003

DO_NOT_REPEAT_FINGERPRINT=sha256-f052d2b471d48f07
