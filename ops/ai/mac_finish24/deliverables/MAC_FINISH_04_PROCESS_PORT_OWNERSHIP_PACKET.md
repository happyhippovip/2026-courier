# MAC-FINISH-04 — Process & Port Ownership Packet

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-04
- **Area**: PROCESS_PORT_OWNERSHIP_PACKET
- **Host**: macOS (`Darwin 25.6.0 x86_64`)
- **Status**: COMPLETE

Defines process tracking, port ownership, termination sequences, and anti-collision guards.

---

## 2. Port Architecture
- **Port 8080**: Production / Main server (STRICTLY UNTOUCHED).
- **Port 8081**: Dedicated Staging Port for physical validation (`RUN_1`, `RUN_2`).
- **Port 8082**: Dedicated Mirror / Telemetry Dashboard (Optional read-only).

---

## 3. Process Lifecycle & PID Tracking
- Staging coordinator PID is recorded in `server/state/staging.pid`.
- Pre-flight check asserts no rogue process: `lsof -i :8081` must return empty (exit code 1).
- Termination sequence:
  1. `kill -TERM ${PID}`
  2. Poll loop for 5 seconds waiting for clean process exit.
  3. If still alive after 5s: `kill -KILL ${PID}`.
  4. Assert port 8081 is unallocated.

---

## 4. Heavy Job Mutual Exclusion
- File lock `/tmp/courier_heavy_job.lock` ensures `MAX_HEAVY_JOBS=1`.
- Lock acquisition uses `flock` or atomic `O_CREAT | O_EXCL`.
