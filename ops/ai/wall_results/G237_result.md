# Result for G237: Worker disappears recovery

TASK_ID=G237
STATUS=PROVEN
HOST=MAC
PROVIDER=GOOGLE_CLI
INPUTS_READ=scripts/courier_watchdog.py, server/app.py
RESULTS_REUSED=scripts/courier_watchdog.py, server/app.py
OUTPUT_REF=Disappeared worker detected via missed heartbeats / claim timeout; attempt logged as `ABANDONED` and task returned to `READY` with attempt counter incremented.
MISSING=None
BLOCKER=None
NEXT_DEPENDENCY=NONE
DO_NOT_REPEAT_FINGERPRINT=G237_WORKER_DISAPPEARS_RECOVERY_PROVEN

DO_NOT_REPEAT_FINGERPRINT=sha256-b94c5950c007062f
