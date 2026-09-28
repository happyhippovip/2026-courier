# Result for GLEDGER-126: Server persistence gap map

TASK_ID=GLEDGER-126
STATUS=PROVEN
HOST=MAC
PROVIDER=GOOGLE
INPUTS_READ=server/app.py:367, ops/ai/coordination_reports/FAMILY_18_CENTRAL_WRITER_COMPRESSED.md
RESULTS_REUSED=server/app.py:367, ops/ai/coordination_reports/FAMILY_18_CENTRAL_WRITER_COMPRESSED.md
OUTPUT_REF=Server persistence gap: Line 367 duplicate check compares only (dispatch_id, result_id, status). Required fix: expand to (dispatch_id, result_id, status, worker_id, attempt_id). Packaged for CW.
MISSING=None
BLOCKER=None
NEXT_DEPENDENCY=GLEDGER-127
DO_NOT_REPEAT_FINGERPRINT=gledger-126-server-persistence-gap-map-v1

DO_NOT_REPEAT_FINGERPRINT=sha256-0bc3cd4d510cbfde
