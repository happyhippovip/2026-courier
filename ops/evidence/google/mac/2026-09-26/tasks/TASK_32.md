# TASK_32 — Conflicting Duplicate Result

STATUS=DONE
FILE_LINE_EVIDENCE=server/app.py:352-415

CURRENT_BEHAVIOR=REJECTED (HTTP 409 or 400) — first-write-wins; second conflicting result for same dispatch rejected
IDENTITY_KEYS=result_id (dispatch-bound)
PROTECTION=result_id already stored → reject with error; state not mutated
RISK=LOW — first result wins; attacker cannot inject conflicting result
SAFE_FOR_CANARY_1=YES
DELIVERY_RETRY=N/A (this is a different dispatch scenario)
EXECUTION_RETRY=Not triggered by server; would require explicit reclaim
UNKNOWN=Exact HTTP error code for conflict (400 vs 409) not audited in candidate-b-1 line-by-line; behavior is reject.
