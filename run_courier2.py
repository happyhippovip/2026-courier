import os
import sys
from pathlib import Path
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
from scripts.courier_real_worker_adapters import get_real_worker_adapters
from scripts.courier_founder_mode import FounderModeMVP

workspace = os.getcwd()
dispatcher = CourierSafetyDispatcher(workspace)
adapters = get_real_worker_adapters(Path(workspace))
for agent, adapter in adapters.items():
    dispatcher.adapter_boundary.register_consumer(agent, adapter)

mvp = FounderModeMVP(workspace_dir=workspace, dispatcher=dispatcher)
mvp.intake.set_status("ef3c716c-a053-43fb-9bba-864f8395764b", "PENDING")

goal = mvp.intake.pop_next_goal()
completed_missions = []
next_missions = mvp.planner.discover_and_plan(goal, completed_missions)
for m in next_missions:
    m_id = mvp.queue.enqueue(m)
    print(f"Enqueued: {m_id}")

pending = [m for m in mvp.queue.read_all() if m["status"] == "PENDING"]
worker_id = "test_worker"
mission_result = mvp.dispatcher.process_next_mission(worker_id)
print(f"Mission Result: {mission_result}")

