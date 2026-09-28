# Result for G192: Partial-write recovery check

TASK_ID=G192
STATUS=PROVEN
HOST=MAC
PROVIDER=GOOGLE_CLI
INPUTS_READ=server/app.py, scripts/integration_contract.py
RESULTS_REUSED=server/app.py, scripts/integration_contract.py
OUTPUT_REF=If process crashes mid-write, partial `.tmp` files are ignored/cleaned on startup. Target `central_state.json` retains previous valid checkpoint. Fail-closed behavior on corrupted state.
MISSING=None
BLOCKER=None
NEXT_DEPENDENCY=NONE
DO_NOT_REPEAT_FINGERPRINT=G192_PARTIAL_WRITE_RECOVERY_PROVEN

DO_NOT_REPEAT_FINGERPRINT=sha256-d1d5566158df453e
