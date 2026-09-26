# TASK_39 — New Attempt After FAILED

STATUS=DONE

CURRENT_BEHAVIOR=New attempt gets new attempt_id, new dispatch_id, new result_id binding.
Prior attempt's artifacts are NOT re-used (new upload required).
IDENTITY_KEYS=attempt_id + dispatch_id (both fresh on retry)
PROTECTION=Old result_id bound to old dispatch → rejected by server if submitted for new dispatch
RISK=LOW — fresh attempt is fully isolated from prior attempt
SAFE_FOR_CANARY_1=YES
DELIVERY_RETRY=Fresh — no stale artifact reuse
EXECUTION_RETRY=Full re-execution; deterministic artifact → same hash → same expected_sha256 → PASS
UNKNOWN=None
