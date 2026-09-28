# M213 — Server Crash Simulation & Hard-Kill Injection Point Definition

## 1. Overview & Authority
- **Task ID**: M213
- **Area**: CRASH_SIMULATION
- **Status**: COMPLETE

## 2. Crash Injection Protocol
- Injection method: `kill -9 $(cat server/state/staging.pid)`.
- Trigger moment: After Task A persistence cutpoint, prior to Task B dispatch completion.
- Verification: Process exits instantaneously with zero graceful cleanup.
