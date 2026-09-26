# TASK_08: Occupied Ports & Collision-Free Canary Port

STATUS=DONE
NEW_EVIDENCE=lsof -iTCP -sTCP:LISTEN inspection: Port 8080 is LISTEN by Python PID 69407. Port 5000 is LISTEN by Apple ControlCenter (AirPlay PID 531). Port 8081 is FREE and verified unallocated.
PROVEN=Port 8080 = OCCUPIED (production). Port 8081 = FREE (Canary 1 target port).
UNKNOWN=None
BLOCKER=None
NEXT=TASK_09
