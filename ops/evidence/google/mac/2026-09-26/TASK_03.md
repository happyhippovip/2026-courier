# TASK_03: Inventory Active Courier Processes

**HOST:** MAC
**ROLE:** PHYSICAL_CANARY_PREPARATION_OWNER
**DATE:** 2026-09-26
**TARGET_REPO:** /Users/user/Downloads/2026-courier

---

STATUS=COMPLETE
NEW_EVIDENCE=ps -eo pid,command and lsof confirm single server, verifier, and worker instances.
PROVEN=Active processes: Server PID 69407 (port 8080), Verifier PID 42002, Worker PID 46250. Supervisor is inactive. Background pool contains 10 lease-renewal heartbeats.
UNKNOWN=None.
BLOCKER=None.
NEXT=TASK_04
