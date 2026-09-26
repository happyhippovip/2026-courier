# TASK_33 — Stale Attempt Result

STATUS=DONE
FILE_LINE_EVIDENCE=server/app.py + scripts/integration_contract.py (validate_durable_result)

CURRENT_BEHAVIOR=REJECTED — attempt_id and dispatch_id are validated against current task state; stale attempt rejected
IDENTITY_KEYS=attempt_id + dispatch_id (both must match current task dispatch)
PROTECTION=validate_durable_result checks all 9 binding fields; stale attempt_id → mismatch → 400
RISK=LOW — stale results cannot advance task state
SAFE_FOR_CANARY_1=YES
DELIVERY_RETRY=SAFE (retry with correct attempt_id)
EXECUTION_RETRY=Only on explicit reclaim + new dispatch
UNKNOWN=None
