# Result for G209: Duplicate response contract

TASK_ID=G209
STATUS=PROVEN
HOST=MAC
PROVIDER=GOOGLE_CLI
INPUTS_READ=server/app.py, scripts/integration_contract.py
RESULTS_REUSED=server/app.py, scripts/integration_contract.py
OUTPUT_REF=Duplicate response contract: Identical replay -> HTTP 200 `{'status': 'DUPLICATE_ACCEPTED'}`; Conflicting replay -> HTTP 409 `{'error': 'CONFLICTING_RESULT_REPLAY'}`.
MISSING=None
BLOCKER=None
NEXT_DEPENDENCY=NONE
DO_NOT_REPEAT_FINGERPRINT=G209_DUPLICATE_RESPONSE_CONTRACT_PROVEN

DO_NOT_REPEAT_FINGERPRINT=sha256-59b88411c2d28b8d
