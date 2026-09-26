# TASK_12: Trace artifact_id -> Server-Side Artifact

**HOST:** MAC
**ROLE:** PHYSICAL_CANARY_PREPARATION_OWNER
**DATE:** 2026-09-26
**TARGET_REPO:** /Users/user/Downloads/2026-courier

---

STATUS=COMPLETE
NEW_EVIDENCE=scripts/artifact_store.py:120-145; server/app.py:375-385.
PROVEN=Server validates artifact_id against records/<artifact_id>.json and confirms immutable binding to task_id, attempt_id, and dispatch_id.
UNKNOWN=None.
BLOCKER=None.
NEXT=TASK_13
