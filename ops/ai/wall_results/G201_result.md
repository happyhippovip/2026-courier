# Result for G201: Duplicate canonicalization audit

TASK_ID=G201
STATUS=PROVEN
HOST=MAC
PROVIDER=GOOGLE_CLI
INPUTS_READ=server/app.py, tests/test_p3_server_idempotency.py
RESULTS_REUSED=server/app.py, tests/test_p3_server_idempotency.py
OUTPUT_REF=Canonical duplicate comparison fields verified: 5-tuple (`task_id`, `attempt_id`, `worker_id`, `status`, canonical artifact digests).
MISSING=None
BLOCKER=None
NEXT_DEPENDENCY=NONE
DO_NOT_REPEAT_FINGERPRINT=G201_DUPLICATE_CANONICALIZATION_AUDIT_PROVEN

DO_NOT_REPEAT_FINGERPRINT=sha256-a0c05c694802e793
