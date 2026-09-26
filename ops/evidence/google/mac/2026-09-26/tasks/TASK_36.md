# TASK_36: Duplicate / Retry: RESULT_READY Resend After Lost ACK

STATUS=DONE
NEW_EVIDENCE=Worker loses network response after server processed result. Worker retries delivery of RESULT_READY. Server recognizes result_id, responds ACK_DUPLICATE. Worker transitions to DONE.
PROVEN=Delivery retry after lost ACK succeeds cleanly without side effects.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_37
