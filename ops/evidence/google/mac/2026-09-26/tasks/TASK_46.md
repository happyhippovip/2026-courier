# TASK_46: Physical Run Prep: Before/After Restart Identity Comparison

STATUS=DONE
NEW_EVIDENCE=Comparison keys: goal_id, task_id, attempt_id, dispatch_id, result_id, artifact sha256. Assert all pre-crash IDs byte-identical in reloaded post-crash state.
PROVEN=Identity preservation test protocol verified in test_p3_server_idempotency.py (35/35 passing).
UNKNOWN=None
BLOCKER=None
NEXT=TASK_47
