# TASK_06: Muse CLI vs Adapter Expectations

**HOST:** MAC
**ROLE:** PHYSICAL_CANARY_PREPARATION_OWNER
**DATE:** 2026-09-26
**TARGET_REPO:** /Users/user/Downloads/2026-courier

---

STATUS=COMPLETE
NEW_EVIDENCE=Direct execution: unsupported reasoning effort `auto`; expected none|minimal|low|medium|high|xhigh|max|ultra.
PROVEN=Adapter in scripts/muse_wall_supervisor.py passes --reasoning-effort auto by default. Physical CLI requires an explicit level (e.g. high) or omission.
UNKNOWN=None.
BLOCKER=M45-MUSE-CLI-REASONING-EFFORT-01 must be patched to 'high' before running Muse supervisor tasks.
NEXT=TASK_07
