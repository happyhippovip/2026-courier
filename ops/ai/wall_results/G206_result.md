# Result for G206: Conflicting replay persistence

TASK_ID=G206
STATUS=PROVEN
HOST=MAC
PROVIDER=GOOGLE_CLI
INPUTS_READ=server/app.py, tests/test_p3_server_idempotency.py
RESULTS_REUSED=server/app.py, tests/test_p3_server_idempotency.py
OUTPUT_REF=Incoming result with matching `task_id` and `attempt_id` but conflicting hash/status is rejected with HTTP 409 Conflict. Stored canonical state is unaltered.
MISSING=None
BLOCKER=None
NEXT_DEPENDENCY=NONE
DO_NOT_REPEAT_FINGERPRINT=G206_CONFLICTING_REPLAY_PERSISTENCE_PROVEN

DO_NOT_REPEAT_FINGERPRINT=sha256-c53b6ca1721d107f
