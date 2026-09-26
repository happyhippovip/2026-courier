# TASK_31: Identical Duplicate Result Handling

**HOST:** MAC
**ROLE:** PHYSICAL_CANARY_PREPARATION_OWNER
**DATE:** 2026-09-26
**TARGET_REPO:** /Users/user/Downloads/2026-courier

---

STATUS=COMPLETE
NEW_EVIDENCE=server/app.py:365; test_resent_result_is_acknowledged_idempotently.
PROVEN=Resending identical (dispatch_id, result_id, status) returns HTTP 200 with {'status': 'ACK_DUPLICATE'} without side effects.
UNKNOWN=None.
BLOCKER=None.
NEXT=TASK_32
