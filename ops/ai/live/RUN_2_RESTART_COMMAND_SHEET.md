# RUN_2 Restart Command Sheet

## 1. Objective
- Execute a **controlled restart** following a successful RUN_1 or specific interruption.
- Ensure **A persistence**: The state of Phase A must be preserved and recognized.
- Enforce **no A replay**: Phase A must not be executed again (A execution count = 1).
- Perform **reconcile resume**: Reconstruct runtime state from existing checkpoints.
- Trigger **B continuation**: Seamlessly begin executing Phase B.

## 2. Pre-requisites
- **CRITICAL CONSTRAINT:** Keine Ausführung vor RUN_1 PASS. RUN_2 darf erst gestartet werden, wenn RUN_1 vollständig evaluiert und auf PASS gesetzt wurde.
- Validation: `runs/run_001/artifacts/run_manifest.json` must indicate `A_STATUS: COMPLETED`.

## 3. Restart Commands
- **Reconciliation Check:** 
  `python3 -m src.main reconcile --target run_001 --verify-phase A`
- **Controlled Restart (Resume):**
  `python3 -m src.main resume --run-id run_002 --base-state run_001 --skip A --start B`
- **State Assertion:**
  `python3 -m ops.assert_state --phase A --expected-count 1`

## 4. Execution Directives
- **Controlled Restart:** Boot the `ResourceAdmissionController` and `ProcessOwnershipManager` but inject the hydrated state from the `runs/run_001/state/` directory.
- **A Execution Count:** Must be strictly locked to `1`. The reconciliation engine will abort if Phase A attempts to boot.
- **B Continuation:** The dispatcher must queue Phase B workloads directly upon successful `reconcile resume`.

## 5. Teardown / Verification
- Once Phase B completes, verify that Phase A was entirely skipped in the runtime logs (`grep "Executing Phase A" runs/run_002/logs/system.log` must yield nothing).
