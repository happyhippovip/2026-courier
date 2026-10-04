# M209: DONE -> SUCCESS Rewrite

## Goal
Standardize terminology across the Courier system by converting the final goal/result status from `"DONE"` to `"SUCCESS"`. This ensures consistency with the worker result envelope (which uses `"SUCCESS"` vs `"FAILED"`) and standardizes terminology across all validation and relay layers.

## Implementation & Proof
1. **Control Plane (`server/app.py`)**:
   - Modified the reconciliation logic (`verify_task_result`). When a workflow plan completes all steps (`current_step_index >= len(workflow_plan)`), the goal status is now mutated to `"SUCCESS"` instead of `"DONE"`.
2. **Couriers & Relays**:
   - `scripts/consume_chief_command.py`: Updated terminal evaluation to set `result_status = "SUCCESS"`.
   - `scripts/publish_courier_result.py`: Adjusted strict envelope validation to demand `result["status"] == "SUCCESS"` for the terminal transmission to Codex.
   - `scripts/validate_chief_relay.py`: Updated allowable inbound goal status to `{"SUCCESS", "FAILED", "BLOCKED"}`.
3. **Acceptance Testing**:
   - `tests/test_courier_motor_precheck.py` and `tests/test_server_integration_contract.py` assertions updated to reflect the new state space.

## Conclusion
The vocabulary mismatch has been completely eradicated across the Courier and Chief pipelines.
