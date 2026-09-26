# TASK_11: Trace: Worker Result -> Artifact ID

STATUS=DONE
NEW_EVIDENCE=Trace daemon.py:126-155 -> integration_contract.py:112-120. Worker executes instruction, captures output file, hashes via hashlib.sha256, constructs payload artifacts: [{'path': p, 'sha256': digest}], generates UUID result_id.
PROVEN=Result payload binds task_id, attempt_id, dispatch_id, run_id, result_id, and artifact digest list.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_12
