# TASK_05: Muse CLI Argument Contract

**HOST:** MAC
**ROLE:** PHYSICAL_CANARY_PREPARATION_OWNER
**DATE:** 2026-09-26
**TARGET_REPO:** /Users/user/Downloads/2026-courier

---

STATUS=COMPLETE
NEW_EVIDENCE=muse exec --help and physical test run confirmed exact syntax requirements.
PROVEN=Muse CLI supports: exec, --workspace <PATH>, --yolo, --disable-approval, --session-id <UUID>, --json, and --reasoning-effort <none|minimal|low|medium|high|xhigh|max|ultra>. 'auto' is rejected with exit code 2.
UNKNOWN=None.
BLOCKER=Adapter passing 'auto' causes immediate CLI failure.
NEXT=TASK_06
