# M202 — Server Process Lifecycle & PID File Ownership

## 1. Overview & Authority
- **Task ID**: M202
- **Area**: PID_OWNERSHIP
- **Status**: COMPLETE

## 2. PID File Contract
- Path: `server/state/staging.pid`.
- On startup: Write PID of coordinator process.
- On shutdown: Validate PID still belongs to process, then delete file.
- Stale detection: If PID file exists but `kill(pid, 0)` fails with `ESRCH`, reclaim stale file.
