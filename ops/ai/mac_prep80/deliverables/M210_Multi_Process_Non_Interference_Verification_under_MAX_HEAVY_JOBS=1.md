# M210 — Multi-Process Non-Interference Verification under MAX_HEAVY_JOBS=1

## 1. Overview & Authority
- **Task ID**: M210
- **Area**: RESOURCE_GUARD
- **Status**: COMPLETE

## 2. Resource Guard
- Enforces strict concurrency ceiling: at most 1 heavy task (test runner or server process) active at any instant.
- Lightweight operations (ledger recording, hash verification) run sequentially.
- Prevents CPU throttling or memory exhaustion on host.
