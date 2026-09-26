# TASK_32: Conflicting Duplicate Result Handling

**HOST:** MAC
**ROLE:** PHYSICAL_CANARY_PREPARATION_OWNER
**DATE:** 2026-09-26
**TARGET_REPO:** /Users/user/Downloads/2026-courier

---

STATUS=COMPLETE
NEW_EVIDENCE=server/app.py:370; test_conflicting_result_for_processed_task_is_rejected.
PROVEN=Submitting a conflicting result for an already-processed task returns HTTP 409 Conflict.
UNKNOWN=None.
BLOCKER=None.
NEXT=TASK_33
