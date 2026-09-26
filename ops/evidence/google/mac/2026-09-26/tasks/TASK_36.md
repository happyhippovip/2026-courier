# TASK_36 — RESULT_READY Resend After Lost ACK

STATUS=DONE

CURRENT_BEHAVIOR=SAFE — idempotent (candidate-b-1); ACK_DUPLICATE returned for same result_id
IDENTITY_KEYS=result_id
PROTECTION=Server stores result exactly once; re-send with same result_id → ACK_DUPLICATE
RISK=LOW — lost ACK triggers safe retry; no double-store
SAFE_FOR_CANARY_1=YES
DELIVERY_RETRY=SAFE and idempotent
EXECUTION_RETRY=NONE triggered — task stays RESULT_RECEIVED after first submission
UNKNOWN=Production 332a42f9 may not have idempotency patch (candidate-b-1 adds it)
