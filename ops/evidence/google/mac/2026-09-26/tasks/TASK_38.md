# TASK_38 — FAILED → Requeue Behavior

STATUS=DONE

CURRENT_BEHAVIOR=FAILED tasks are requeued as READY after reclaim_stale (if within retry limit).
PROTECTION=attempt_id incremented on requeue; old attempt result rejected.
RISK=LOW for Canary 1 (deterministic artifact; retry produces same result)
SAFE_FOR_CANARY_1=YES
DELIVERY_RETRY=N/A (FAILED is a worker-submitted status)
EXECUTION_RETRY=YES — new attempt_id + dispatch_id; fresh execution
UNKNOWN=Max retry limit for FAILED requeue (not audited in candidate-b-1).
