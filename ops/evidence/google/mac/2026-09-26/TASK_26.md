# TASK_26: Worker-Reported SHA Alone Cannot Produce PASS

**HOST:** MAC
**ROLE:** PHYSICAL_CANARY_PREPARATION_OWNER
**DATE:** 2026-09-26
**TARGET_REPO:** /Users/user/Downloads/2026-courier

---

STATUS=COMPLETE
NEW_EVIDENCE=scripts/courier_verifier.py:74 computes hashlib.sha256(data).hexdigest() directly from fetched stream.
PROVEN=Verifier independently hashes downloaded server-side bytes and ignores self-reported worker hash if bytes mismatch.
UNKNOWN=None.
BLOCKER=None.
NEXT=TASK_27
