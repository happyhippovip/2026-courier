# N2: RUN1_TO_RUN2_GATE

## Goal
Implement a strict gate between `RUN_1` and `RUN_2` execution phases to ensure that `RUN_2` (the crash recovery and durability proof) only runs if `RUN_1` (the isolated execution) completed successfully and passed all verifications.

## Context
The Courier marathon uses a sequence of execution scripts (`run_1_mac.sh`, `run_2_mac.sh`) to prove both clean process isolation (Run 1) and crash/recovery capability (Run 2). If Run 1 fails (e.g. `courier_verifier` detects a failure or error), it is invalid to proceed to Run 2, as Run 2 relies on a valid persisted state to simulate recovery. Running Run 2 on a corrupted or failed Run 1 state could result in false positives or masking of underlying bugs.

## Implementation Details

1. **RUN_1 Success Marker:**
   In `run_1_mac.sh`, the script now explicitly captures the exit code of `courier_verifier`:
   ```bash
   python3 -m scripts.courier_verifier --target=A > logs/verifier_run1.log 2>&1
   if [ $? -eq 0 ]; then
       echo "RUN_1 completed successfully. Authorizing RUN_2."
       touch artifacts/RUN_1_SUCCESS
   else
       echo "ERROR: RUN_1 verification failed."
       exit 1
   fi
   ```
   This creates an explicit boolean authorization ticket (`artifacts/RUN_1_SUCCESS`) for the next phase.

2. **RUN_2 Preflight Validation:**
   In `run_2_mac.sh`, before touching any state or killing any processes, a strict gate check is enforced:
   ```bash
   echo "== N2: RUN1_TO_RUN2_GATE Validation =="
   if [ ! -f "artifacts/RUN_1_SUCCESS" ]; then
       echo "ERROR: RUN_2 aborted. RUN_1 did not complete successfully (missing artifacts/RUN_1_SUCCESS)."
       exit 1
   fi
   ```
   This prevents Run 2 from attempting to read from `ledger_run1.db` if the previous step failed to produce a valid proof state.

3. **Validation Test:**
   A test file `tests/test_n2_run1_to_run2_gate.py` has been added to prove that `run_2_mac_mock.sh` behavior strictly adheres to this contract (failing if `artifacts/RUN_1_SUCCESS` is absent, succeeding if it is present).

## Conclusion
The `RUN1_TO_RUN2_GATE` acts as a crucial checkpoint, guaranteeing that the mission pipeline fails fast and loud upon the first sign of execution divergence, preserving the integrity of the durability and replay physical proofs.
