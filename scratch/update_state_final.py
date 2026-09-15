import json
import time
import os

state_file = "events/runtime-state/CONTINUATION_STATE.json"
with open(state_file, "r") as f:
    state = json.load(f)

state["LAST_COMPLETED_TASK"] = "plan-imp-bbb4d93b"
state["LAST_RESULT"] = "SUCCESS: Courier Step 8 completed cleanly. AUTONOMY_LIVE_REPORT.md generated and verified."
state["LAST_EVALUATION"] = "The integrated Gemini loop works. Result consumed, acknowledged, and task marked COMPLETED by orchestrator."
state["CURRENT_TASK"] = None
state["NEXT_SAFE_TASK"] = "Transition to Step 9: Integrate Windows AI OS worker output directly into multi-step goal completion."
state["UPDATED_AT"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
state["BLOCKERS"] = []

tmp = state_file + ".tmp"
with open(tmp, "w") as f:
    json.dump(state, f, indent=4)
os.replace(tmp, state_file)
print("Updated CONTINUATION_STATE.json atomically for Step 8 completion.")
