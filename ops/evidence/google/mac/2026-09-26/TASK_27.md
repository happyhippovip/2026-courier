# TASK_27: Behavior When expected_sha256 Missing

**HOST:** MAC
**ROLE:** PHYSICAL_CANARY_PREPARATION_OWNER
**DATE:** 2026-09-26
**TARGET_REPO:** /Users/user/Downloads/2026-courier

---

STATUS=COMPLETE
NEW_EVIDENCE=Candidate B verifier logic branches conditionally on 'if expected_sha256 in art'.
PROVEN=If expected_sha256 is omitted, verifier validates artifact existence and schema without content check.
UNKNOWN=None.
BLOCKER=None.
NEXT=TASK_28
