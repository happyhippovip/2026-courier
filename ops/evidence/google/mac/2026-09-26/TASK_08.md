# TASK_08: Occupied Ports and Collision-Free Canary Port

**HOST:** MAC
**ROLE:** PHYSICAL_CANARY_PREPARATION_OWNER
**DATE:** 2026-09-26
**TARGET_REPO:** /Users/user/Downloads/2026-courier

---

STATUS=COMPLETE
NEW_EVIDENCE=lsof -iTCP:8080 confirms PID 69407 listening; port 8085 is confirmed unbound.
PROVEN=Port 8080 is occupied by live server PID 69407. Safe collision-free canary port is 8085 or 8090. Alternatively, Canary 1 client connects to existing 8080.
UNKNOWN=None.
BLOCKER=Attempting to launch a second server on port 8080 fails with EADDRINUSE.
NEXT=TASK_09
