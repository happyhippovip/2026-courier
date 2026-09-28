# Result for G205: Duplicate after process reload

TASK_ID=G205
STATUS=PROVEN
HOST=MAC
PROVIDER=GOOGLE_CLI
INPUTS_READ=server/app.py, tests/test_p3_server_idempotency.py
RESULTS_REUSED=server/app.py, tests/test_p3_server_idempotency.py
OUTPUT_REF=Persisted records in `central_state.json` serve as source of truth across reloads. Replayed identical result post-restart successfully returns HTTP 200 duplicate response.
MISSING=None
BLOCKER=None
NEXT_DEPENDENCY=NONE
DO_NOT_REPEAT_FINGERPRINT=G205_DUPLICATE_POST_RELOAD_PROVEN

DO_NOT_REPEAT_FINGERPRINT=sha256-2ebf4ec541977dd6
