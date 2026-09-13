import sys
import json
import os
from pathlib import Path

def main():
    try:
        input_data = json.load(sys.stdin)
    except:
        input_data = {}

    state_file = Path("../.courier_state/mac_autonomy_state.json")
    if not state_file.exists():
        print(json.dumps({"decision": "stop", "reason": f"No autonomy state found at {state_file.resolve()}"}))
        return

    with open(state_file, "r") as f:
        try:
            state = json.load(f)
        except:
            print(json.dumps({"decision": "stop", "reason": "Malformed autonomy state."}))
            return

    # Check CONTINUATION_SAFETY_CONDITIONS
    # If safe_local_work_exists AND no conflicting writer AND no branch-local human gate
    if state.get("NEXT_SAFE_TASK") and state.get("ACTIVE_WRITER") is None and not state.get("HUMAN_GATES"):
        if state.get("CONTINUATION_DECISION") == "CONTINUE":
            print(json.dumps({
                "decision": "continue",
                "reason": f"Autonomous continuation: {state.get('NEXT_SAFE_TASK')}"
            }))
            return
            
    print(json.dumps({"decision": "stop", "reason": "No safe tasks or blocked by human gate."}))

if __name__ == "__main__":
    main()
