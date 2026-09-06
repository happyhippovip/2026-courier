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

print("Starting Autonomous Loop with 30m timeout...")
mvp.run_autonomous_loop()
print("Done.")
