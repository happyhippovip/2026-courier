# M207: Physical Exit Code Truth

## Goal
Prove that the worker process accurately captures and transmits the physical exit code of the execution to the control plane, and that the durable result validation strictly correlates the physical exit code to the logical status (`SUCCESS` <=> `exit_code == 0`).

## Implementation
1. **Integration Contract (`scripts/integration_contract.py`)**:
   - Updated `validate_durable_result` to require the `exit_code` field.
   - Enforced strict semantics: if `status` is `SUCCESS`, `exit_code` must be exactly 0. If `status` is `FAILED`, `exit_code` must be non-zero.
2. **Windows Daemon (`scripts/windows_worker/daemon.py`)**:
   - Modified the execution loop to accurately capture the PowerShell `process.returncode` and append it to `res_json` as `"exit_code"`.
   - In the event of an unhandled exception before process completion, `exit_code` is set to `-1` to ensure a non-zero value aligns with the `FAILED` status.
3. **Mac Daemon (`scripts/mac_worker/daemon.py`)**:
   - Already includes `"exit_code": result.returncode` during execution.

## Proof
The `validate_durable_result` check acts as the gatekeeper for DurableResults entering the system. Because `exit_code` is now mathematically bound to the semantic `status`, it is mathematically impossible for a worker to mask a non-zero physical exit code as a `SUCCESS` status without triggering a `ContractError`.
