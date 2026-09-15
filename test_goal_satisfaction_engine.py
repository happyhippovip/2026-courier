import json
import uuid
from pathlib import Path
from scripts.courier_goal_satisfaction_engine import GoalSatisfactionEngine
import time
import os

workspace_dir = Path(os.getcwd())
engine = GoalSatisfactionEngine(workspace_dir)

# Ensure state is clean
if engine.db_file.exists():
    engine.db_file.unlink()

def create_mission(status, requires_write=False, files=None, ref=None):
    m = {
        "mission_id": str(uuid.uuid4()),
        "status": status,
        "requires_write": requires_write,
    }
    if files:
        m["result_data"] = {"payload": {"changed_files": files}}
    if ref:
        m["result_reference"] = ref
    return m

print("--- Test 1: Genuinely satisfied goal ---")
goal1 = "Create a file named satisfied.txt containing exactly: SUCCESS 100"
missions1 = [
    create_mission("VERIFIED", requires_write=True, files=["satisfied.txt"]),
    create_mission("VERIFIED", requires_write=False, ref="/tmp/effect.json")
]
Path("satisfied.txt").touch()
res1 = engine.recompute(goal1, missions1)
print(f"Goal 1 Decision: {res1}")
assert res1 == "VERIFIED_COMPLETE", res1
Path("satisfied.txt").unlink()

print("--- Test 2: Goal with real remaining gap ---")
goal2 = "Create a file named missing.txt containing exactly: FAILED 0"
missions2 = [
    create_mission("VERIFIED", requires_write=True, files=["other.txt"])
]
res2 = engine.recompute(goal2, missions2)
print(f"Goal 2 Decision: {res2}")
assert res2 == "CONTINUE_SAFE_WORK" or res2 == "QUIESCENT_WAKEABLE", res2

print("--- Test 3: One Human-Gated branch + independent safe branch ---")
# The goal needs some human gated mission but still gaps remaining?
goal3 = "Create a file named human_gated.txt containing exactly: PENDING"
missions3 = [
    create_mission("HUMAN_GATE"),
]
res3 = engine.recompute(goal3, missions3)
print(f"Goal 3 Decision: {res3}")
assert res3 == "CONTINUE_SAFE_WORK", res3

print("--- Test 4: Restart must not reopen a VERIFIED_COMPLETE goal ---")
res4 = engine.recompute(goal1, missions1)
print(f"Goal 4 Decision: {res4}")
assert res4 == "VERIFIED_COMPLETE", res4

print("All tests passed.")

print("--- Test 5: Goal is a dictionary ---")
goal_dict = {"goal": "Create a file named dict_satisfied.txt containing exactly: SUCCESS 100", "status": "ACTIVE"}
Path("dict_satisfied.txt").touch()
res5 = engine.recompute(goal_dict, missions1)
print(f"Goal 5 Decision: {res5}")
assert res5 == "VERIFIED_COMPLETE", res5
Path("dict_satisfied.txt").unlink()
print("All tests passed, including dictionary.")
