# Result for G196: Pending-verification survival map

TASK_ID=G196
STATUS=PROVEN
HOST=MAC
PROVIDER=GOOGLE_CLI
INPUTS_READ=server/app.py, scripts/courier_verifier.py
RESULTS_REUSED=server/app.py, scripts/courier_verifier.py
OUTPUT_REF=Tasks in `RESULT_RECEIVED` state retain pending status across server restart. Verifier daemon polls and drains pending queue upon recovery without rerunning worker code.
SOURCE-TRUTH-CORRECTION=2026-09-28: `SUBMITTED`/`READY` are not implemented Courier task states (TASK_STATES in scripts/integration_contract.py:16-24; server/app.py sets RESULT_RECEIVED at :382,386 and lists it at :462). No reset-to-READY branch exists in source. Behavior claim holds under the corrected state name.
MISSING=None
BLOCKER=None
NEXT_DEPENDENCY=NONE
DO_NOT_REPEAT_FINGERPRINT=G196_PENDING_VERIFICATION_SURVIVAL_MAPPED

DO_NOT_REPEAT_FINGERPRINT=sha256-5b75eaef8bf0418a
