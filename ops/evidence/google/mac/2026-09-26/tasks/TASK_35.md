# TASK_35 — Result-ID Mismatch

STATUS=DONE
FILE_LINE_EVIDENCE=server/app.py (verify_task_result checks result_id match)

CURRENT_BEHAVIOR=REJECTED — if verify payload result_id ≠ task["result"]["result_id"], verify is rejected
IDENTITY_KEYS=result_id
PROTECTION=result_id is bound to dispatch (= "result-" + dispatch_id); mismatch → reject
RISK=LOW — prevents verification of wrong task's result
SAFE_FOR_CANARY_1=YES
DELIVERY_RETRY=N/A — result_id must match exactly
EXECUTION_RETRY=Not triggered
UNKNOWN=None
