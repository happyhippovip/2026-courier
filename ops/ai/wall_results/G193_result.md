# Result for G193: Malformed persisted state check

TASK_ID=G193
STATUS=PROVEN
HOST=MAC
PROVIDER=GOOGLE_CLI
INPUTS_READ=server/app.py
RESULTS_REUSED=server/app.py
OUTPUT_REF=Malformed JSON in persisted state raises JSONDecodeError, triggering quarantine to `.corrupt.{timestamp}` and fail-closed halt with loud logging; never silently resets or fails open.
MISSING=None
BLOCKER=None
NEXT_DEPENDENCY=NONE
DO_NOT_REPEAT_FINGERPRINT=G193_MALFORMED_STATE_CHECK_PROVEN

DO_NOT_REPEAT_FINGERPRINT=sha256-3e839ce18f890f1b
