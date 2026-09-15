import sys, json, os, uuid, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher, MissionQueue

ws_dir = Path("/tmp/courier_test_empty")
import shutil
if ws_dir.exists():
    shutil.rmtree(ws_dir)
dispatcher = CourierSafetyDispatcher(ws_dir)
res1 = dispatcher.process_next_mission("w1", goal="some_goal")
print("Empty goal:", res1["status"])

q = dispatcher.mission_queue
q.enqueue({
    "mission_id": "m1",
    "goal": "some_goal",
    "task": {"action": "do it"},
    "status": "PENDING"
})
q.transition("m1", "CLAIMED")
q.transition("m1", "RUNNING")
q.transition("m1", "PENDING_VERIFY")
q.transition("m1", "VERIFIED")

res2 = dispatcher.process_next_mission("w1", goal="some_goal")
print("Verified goal:", res2["status"])
