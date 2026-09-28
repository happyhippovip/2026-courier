# Result for G228: Dispatch failure rollback

TASK_ID=G228
STATUS=PROVEN
HOST=MAC
PROVIDER=GOOGLE_CLI
INPUTS_READ=scripts/queue_processor.py, server/app.py
RESULTS_REUSED=scripts/queue_processor.py, server/app.py
OUTPUT_REF=Network or worker spawn failure rolls back task state to `READY` with backoff; attempt counter not incremented and no zombie active dispatch retained.
MISSING=None
BLOCKER=None
NEXT_DEPENDENCY=NONE
DO_NOT_REPEAT_FINGERPRINT=G228_DISPATCH_FAILURE_ROLLBACK_PROVEN

DO_NOT_REPEAT_FINGERPRINT=sha256-66f7abc6259a7eff
