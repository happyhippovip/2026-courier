# Mac Core Freeze Matrix

## Proof Card (GQ38)
The proof card collects real evidence from `RUN_1` and `RUN_2` outputs to definitively assert that the Courier Motor is correctly isolated, correctly handles persistence, verifies accurately without duplication, and reconciles state without error across crash loops.

## Covered Surface (GQ39)
### COVERED
- Task Queue -> Dispatch -> Result Received -> Verified -> Reconciled transition.
- Exact-Once execution for successful tasks.
- No re-dispatching of RECONCILED tasks across crashes.
- Verification hash matching.
- Worker/Verifier Auth boundary separation.

### NOT_COVERED / UNKNOWN
- True network failure midway through chunk upload.
- Mac specific UI elements / physical display requirements.

### HUMAN-DEPENDENT
- `FINAL_SHA` exact authoritative push to `main`.
- Initial repository setup and authentication environment on Mac.

## Core-Freeze-Matrix (GQ40)
- **PROVEN**: Mac HTTP Daemon, `courier_verifier.py`, `integration_contract.py` basic flow.
- **PREPARABLE_NOW**: Auth configuration, run_1_mac.sh, run_2_mac.sh scripts.
- **RUN1_DEPENDENT**: Execution logs for EXACTLY ONCE proof.
- **RUN2_DEPENDENT**: Persistence logs for REPLAY AVOIDANCE proof.
- **BLOCKED**: `FINAL_SHA` durability (WAITING FOR CODEX).

## Retest / Invalidation Triggers (GQ41)
- Trigger 1: Changes to `scripts/integration_contract.py`.
- Trigger 2: Changes to `server/app.py` task state machine.
- Trigger 3: Updating Python version or core dependencies on Mac.

## Windows -> Mac Portability Fingerprints (GQ42)
- Paths must be POSIX. `Path("server/state").resolve()` handles cross-platform well.
- Process IDs and process limits: `lsof` used on Mac, Windows needs `netstat` or `psutil`.
- Replaced Windows specific `msvcrt` locks with cross-platform alternatives or separated locking schemes in `mac_worker/daemon.py`.
