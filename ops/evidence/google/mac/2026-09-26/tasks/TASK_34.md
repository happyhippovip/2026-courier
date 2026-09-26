# TASK_34 — Stale Dispatch Result

STATUS=DONE

CURRENT_BEHAVIOR=REJECTED — dispatch_id in result must match current task["dispatch_id"]; stale dispatch rejected
IDENTITY_KEYS=dispatch_id
PROTECTION=validate_durable_result enforces dispatch_id match
RISK=LOW — old dispatch cannot advance task
SAFE_FOR_CANARY_1=YES
DELIVERY_RETRY=Only valid for current dispatch_id
EXECUTION_RETRY=Not triggered; stale dispatch result is silently rejected (400)
UNKNOWN=None
