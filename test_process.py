from scripts.courier_founder_mode import FounderModeMVP
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
import os

workspace = os.getcwd()
dispatcher = CourierSafetyDispatcher(workspace)
mvp = FounderModeMVP(workspace_dir=workspace, dispatcher=dispatcher)
res = mvp.dispatcher.process_next_mission("founder_loop_1")
print("RESULT:", res)
