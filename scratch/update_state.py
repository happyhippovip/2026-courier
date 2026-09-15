import json
import time
import os

state_file = "events/runtime-state/CONTINUATION_STATE.json"
with open(state_file, "r") as f:
    state = json.load(f)

state["LAST_COMPLETED_TASK"] = "plan-imp-ea791415"
state["LAST_RESULT"] = "SUCCESS: Implemented interactive CLI frontend for POW-001 and wired GET/POST routes into server.py. Verified end-to-end integration."
state["LAST_EVALUATION"] = "Codex was rate-limited, so Antigravity Mac Controller seamlessly picked up the objective and completed the task directly."
state["CURRENT_TASK"] = None
state["NEXT_SAFE_TASK"] = "Run Courier Step 8: generate AUTONOMY_LIVE_REPORT.md via GOOGLE worker using native_agy_runner.py, verifying cross-machine loop."
state["UPDATED_AT"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
state["BLOCKERS"] = []

tmp = state_file + ".tmp"
with open(tmp, "w") as f:
    json.dump(state, f, indent=4)
os.replace(tmp, state_file)
print("Updated CONTINUATION_STATE.json atomically.")
