# TASK_35: Duplicate / Retry: Result-ID Mismatch on Verify

STATUS=DONE
NEW_EVIDENCE=POST /tasks/verify submits result_id differing from task['result']['result_id']. Server returns 400 Bad Request ('result_id mismatch').
PROVEN=Verifier cannot verify unattached or wrong result IDs.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_36
