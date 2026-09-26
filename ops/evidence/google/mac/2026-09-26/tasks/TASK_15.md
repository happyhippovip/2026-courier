# TASK_15: Trace: Verification -> Reconcile

STATUS=DONE
NEW_EVIDENCE=Trace server/app.py:490-495. If verdict == 'PASS': task['status'] = 'RECONCILED'. If verdict == 'FAIL': task['status'] = 'FAILED_VERIFICATION', goal['status'] = 'BLOCKED'.
PROVEN=Reconciliation is conditional on verdict PASS; FAIL transitions fail-closed to BLOCKED.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_16
