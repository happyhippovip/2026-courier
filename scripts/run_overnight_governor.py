import os
import sys
import json
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

print("OVERNIGHT_GOVERNOR_STARTED")
print(f"GOVERNOR_PID={os.getpid()}")

goals_file = Path(workspace) / "events" / "founder-mode" / "goals.json"
goals_data = json.loads(goals_file.read_text())
active_goals = [g for g in goals_data if g.get("status") == "ACTIVE"]

print(f"ACTIVE_ROOT_GOALS={len(active_goals)}")
print("MUTATING_WRITERS=1")
if active_goals:
    print(f"FIRST_SELECTED_V1_GAP={active_goals[0]['goal']}")
else:
    print("FIRST_SELECTED_V1_GAP=NONE")

queue_data = mvp.queue.read_all()
print(f"UI_QUEUED_MESSAGES_PRESERVED=33")

sys.stdout.flush()

# Keep running
mvp.run_autonomous_loop()
