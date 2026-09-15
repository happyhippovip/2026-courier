import json
from pathlib import Path

state_file = Path("events/runtime-state/CONTINUATION_STATE.json")
with open(state_file, "r") as f:
    state = json.load(f)
    
state["LAST_COMPLETED_TASK"] = "WINDOWS_MULTI_STEP_INTEGRATION_PROOF"
state["LAST_RESULT"] = "SUCCESS: Step 9 completed. Windows diagnostic output successfully consumed by Planner and derived into GEMINI task."
state["NEXT_SAFE_TASK"] = "Step 10: Final end-to-end continuous validation."

with open(state_file, "w") as f:
    json.dump(state, f, indent=4)
print("Advanced CONTINUATION_STATE.json to Step 10")
