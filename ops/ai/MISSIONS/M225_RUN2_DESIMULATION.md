# M225: Run2 Desimulation

## Goal
Prove that Courier's acceptance and physical marathon tests completely abandon simulated, mocked workers in favor of genuine host-native process execution.

## Implementation & Proof
1. **Removal of Mock Daemons**:
   - Early versions of the Courier test pipeline simulated worker responses through Python-level function mocks.
2. **Desimulation via Marathon (`run_1`, `run_2`)**:
   - Courier's current architecture uses `run_1` and `run_2` to boot genuine, real-world native processes (`daemon.py`, `courier_verifier.py`).
   - Run 2 explicitly proves crash-recovery desimulation: the server and worker are abruptly restarted, and state is durably parsed from the OS filesystem, exactly mirroring a production outage.

## Conclusion
Courier's Run 1 and Run 2 sequences enforce 100% physical integration truth, eliminating all simulated testing blind spots.
