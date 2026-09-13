import sys
import json
import os
import hashlib
from pathlib import Path

def main():
    try:
        input_data = json.load(sys.stdin)
    except:
        input_data = {}

    script_dir = Path(__file__).parent.resolve()
    repo_root = script_dir.parent
    state_file = repo_root / ".courier_state" / "mac_autonomy_state.json"
    
    if not state_file.exists():
        print(json.dumps({"decision": "stop", "reason": f"No autonomy state found at {state_file}"}))
        return

    with open(state_file, "r") as f:
        try:
            state = json.load(f)
        except:
            print(json.dumps({"decision": "stop", "reason": "Malformed autonomy state."}))
            return
            
    # Loop detection
    history_file = repo_root / ".courier_state" / "hook_history.json"
    state_str = json.dumps(state, sort_keys=True)
    state_hash = hashlib.sha256(state_str.encode()).hexdigest()
    
    history = []
    if history_file.exists():
        try:
            with open(history_file, "r") as f:
                history = json.load(f)
        except:
            pass
            
    if history.count(state_hash) >= 3:
        print(json.dumps({"decision": "stop", "reason": "Loop detected: Identical state repeated 3 times."}))
        return
        
    history.append(state_hash)
    if len(history) > 10:
        history = history[-10:]
    with open(history_file, "w") as f:
        json.dump(history, f)

    # Check CONTINUATION_SAFETY_CONDITIONS
    # We allow continuation if NEXT_SAFE_TASK exists, no ACTIVE_WRITER blocks us, and decision is CONTINUE.
    # An unrelated parked HUMAN_GATE does NOT stop safe internal work.
    if state.get("NEXT_SAFE_TASK") and state.get("ACTIVE_WRITER") is None:
        if state.get("CONTINUATION_DECISION") == "CONTINUE":
            print(json.dumps({
                "decision": "continue",
                "reason": f"Autonomous continuation: {state.get('NEXT_SAFE_TASK')}"
            }))
            return
            
    print(json.dumps({"decision": "stop", "reason": "No safe tasks or blocked by active writer/gate."}))

if __name__ == "__main__":
    main()
