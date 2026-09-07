import os, json
from scripts.courier_founder_mode import FounderModeMVP
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
import uuid

ws = os.getcwd()
d = CourierSafetyDispatcher(ws)
mvp = FounderModeMVP(ws, d)
gid = mvp.intake.submit_goal(source="CLI", goal="this is a test execute a real trade")
goals = mvp.intake.db_file
with open(goals) as f:
    goal_objs = json.load(f)
    goal = next(g for g in goal_objs if g["goal_id"] == gid)

completed_missions = []
next_missions = mvp.planner.discover_and_plan(goal, completed_missions)
for m in next_missions:
    m["mission_id"] = str(uuid.uuid4())
    m["task"]["action"] = "implement_bounded_improvement" # Force it so it's not bypassed
    mvp.queue.enqueue(m)

result = d.process_next_mission("founder_loop_1")
print(result)
status = result.get("status") if result else None
if status == "HUMAN_GATE":
    reason = result.get("reason") or "Worker returned HUMAN_ACTION_REQUIRED or policy blocked the prompt"
    mvp.intake.report_to_chief(gid, "HUMAN_GATE", reason, completed_missions, {}, "HUMAN_REPLAN")
    print("Called report_to_chief")
