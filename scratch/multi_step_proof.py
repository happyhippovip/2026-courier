import json
import time
import subprocess
from pathlib import Path
import sys

# Make sure we can import mac_windows_dispatcher
sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
import mac_windows_dispatcher

def create_and_dispatch(task_id, action):
    print(f"--- Selecting Task: {task_id} ---")
    payload = {
        "TASK_ID": task_id,
        "TARGET_HOST": "windows-ai",
        "PROJECT_PATH": "C:\\Dev\\Windows-AI-OS",
        "ACTION": action
    }
    
    # We call the script as a subprocess to keep isolation and exact same env
    tmp_file = Path(f"/tmp/{task_id}.json")
    with open(tmp_file, "w") as f:
        json.dump(payload, f)
        
    res = subprocess.run(["python3", "scripts/mac_windows_dispatcher.py", str(tmp_file)], capture_output=True, text=True)
    if tmp_file.exists():
        tmp_file.unlink()
        
    return res

print("======================================")
print("MULTI-STEP INTEGRATION PROOF")
print("======================================")

# Task 1
res1 = create_and_dispatch("multi-step-1", "HEALTH_CHECK")
print(res1.stdout)
if res1.returncode != 0:
    print("FAIL on Task 1")
    sys.exit(1)

# Task 2
res2 = create_and_dispatch("multi-step-2", "HEALTH_CHECK")
print(res2.stdout)
if res2.returncode != 0:
    print("FAIL on Task 2")
    sys.exit(1)
    
print("PROOF COMPLETE: MULTI-STEP SUCCESS")
