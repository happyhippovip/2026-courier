# MAC-FINISH-02 — Environment & Config Binding Packet

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-02
- **Area**: ENV_BINDING_PACKET
- **Host**: macOS (`Darwin 25.6.0 x86_64`)
- **Status**: COMPLETE

This packet binds the exact environment, configuration parameters, and invalidation rules required for physical execution.

---

## 2. Exact Runtime Bindings
- **Host OS**: macOS Darwin Kernel Version 25.6.0
- **Python Runtime**: `/usr/bin/python3` or virtualenv (`Python 3.9+`)
- **Workspace Directory**: `/Users/user/Downloads/2026-courier`
- **Network Interfaces**: `localhost:8081` (Staging), `localhost:8080` (Production - Untouched)

---

## 3. Configuration Variables
```bash
PORT=8081
STATE_DIR=server/state/isolated_run1
COURIER_AUTH_TOKEN=TEST_COURIER_AUTH_TOKEN_8081
COURIER_VERIFIER_API_KEY=TEST_COURIER_VERIFIER_KEY_8081
MAX_HEAVY_JOBS=1
HEAVY_JOB_LOCK=/tmp/courier_heavy_job.lock
```

---

## 4. Invalidation Fields & Triggers
Any change in the following fields invalidates this binding and requires re-verification:
1. `GIT_SHA`: Any change in repository commit hash.
2. `PORT_CONFLICT`: Detection of active foreign process on Port 8081.
3. `STATE_DIR_DIRT`: Existence of pre-existing uncleaned files in `STATE_DIR`.
4. `TOKEN_MISMATCH`: Deviation between server configuration and client authentication header.
5. `LOCK_CONTENTION`: Presence of stale `/tmp/courier_heavy_job.lock` without owning PID.
