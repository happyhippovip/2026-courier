# RUN_1, RUN_2, and Core Freeze Preparation Pack
**Prepared on:** Windows Host
**Target Host:** Mac
**Current Phase:** `C WAITING_FOR_CODEX` -> Prepping `D`, `E`, `F`, `G`.

## D. MAC_EXACT_BINDING_PREP
- **FINAL_SHA Target**: Variable depending on Codex success. Currently tracking `3c2aa5160002bdb7e2647ab87a0cef2a6f2a3ec4`.
- **Action**: Mac host MUST `git fetch origin` and `git reset --hard <FINAL_SHA>`. No uncommitted changes allowed before RUN.
- **Key Separation**: Mac execution must NOT share `client_secret.json` or `.env` state with Windows. Clean ledger and credentials must be provisioned for RUN.

## E. RUN_1_PREP
### 1. Isolated Workspace Layout
- `logs/server_run1.log`
- `logs/worker_run1.log`
- `artifacts/run1/`
- `ledger_run1.db` (Isolated, initialized empty or with task A).

### 2. Command Bindings
- **Server**: `python -m server.app --port=8080 --db=ledger_run1.db`
- **Verifier**: `python -m scripts.courier_verifier --target=A`
- **Worker**: `python -m scripts.integration_contract`

### 3. Port & Process Isolation
- Pre-run script must assert `lsof -i :8080` is empty.
- PID files stored in `logs/server.pid` for graceful shutdown.

### 4. Evidence Plans for RUN_1
- **A execution-count evidence**: Worker log must show exactly ONE execution of Task A.
- **expected-hash/server-byte evidence**: `courier_verifier.py` output must be captured, showing expected hash matches exactly what is on the server.
- **A verified/reconciled evidence**: `server_run1.log` must show `Task A status -> RECONCILED`.
- **B auto-dispatch evidence**: Following Task A reconciliation, server must automatically dispatch Task B. Log evidence required.
- **HUMAN_RELAY_COUNT evidence**: `HUMAN_RELAY_COUNT=0` must be asserted. No manual keyboard input during the run.

## F. RUN_2_PREP (Restart & Continuity)
### 1. Controlled Restart Sequence
- Graceful shutdown of server (`kill -SIGTERM <pid>`).
- Restart server binding to the *same* `ledger_run1.db`.
### 2. Evidence Plans for RUN_2
- **Result A persistent**: Server must immediately serve Task A as `RECONCILED`, not `PENDING`.
- **No A replay**: Worker must immediately request work, and server MUST NOT dispatch Task A again. Worker logs must show picking up Task B or being IDLE.

## G. CORE_FREEZE_PREP
- **Source/Build/Runtime Fingerprint**: Mac must capture `sha256sum` of `server/app.py` and `scripts/integration_contract.py` before RUN_1 to prove no tampering.
- **Zero-human A->B evidence**: Combine RUN_1 and RUN_2 logs into a single `MAC_CORE_FREEZE_PROOF.md`.
- **Autonomy Grade**: Target is HIGH autonomy (0 human intervention post-start).

**Status**: PREP_COMPLETE
**Next Legal Phase**: AWAIT_MAC_CANARY (Execution on Mac hardware post-Codex).
