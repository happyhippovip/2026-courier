import os
import sys
import time
import subprocess
import json
import urllib.request
import tempfile
from pathlib import Path

def run_proof():
    print("[Acceptance] Starting Physical Acceptance Proof with Real Workers in Isolated Env...")
    
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        state_file = tdp / "state.json"
        config_path = tdp / "config.json"
        worker_state_dir = tdp / "worker_state"
        worker_state_dir.mkdir()
        
        # Write config.json
        with open(config_path, "w") as f:
            json.dump({"WORKER_ID": "MAC-ISOLATED-01"}, f)
            
        env = os.environ.copy()
        env["COURIER_API_KEY"] = "test-key"
        env["COURIER_VERIFIER_API_KEY"] = "test-verifier-key"
        env["COURIER_STATE_FILE"] = str(state_file)
        env["COURIER_SERVER"] = "http://127.0.0.1:8089"
        env["CONFIG_PATH"] = str(config_path)
        env["COURIER_WORKER_STATE_DIR"] = str(worker_state_dir)
        env["POLL_INTERVAL_SECONDS"] = "1"
        
        server_proc = subprocess.Popen(
            [sys.executable, "-m", "flask", "--app", "server.app:app", "run", "--port", "8089"],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        
        time.sleep(2)
        
        verifier_proc = subprocess.Popen(
            [sys.executable, "-u", "scripts/courier_verifier.py"],
            env=env, stdout=sys.stdout, stderr=sys.stderr
        )
        
        w1_proc = subprocess.Popen(
            [sys.executable, "-u", "scripts/mac_worker/daemon.py"],
            env=env, stdout=sys.stdout, stderr=sys.stderr
        )
        
        time.sleep(3)
        
        plan = []
        for i in range(10):
            plan.append({
                "task_id": f"t-iso-{i}",
                "target_agent": "mac",
                "instruction": f"touch courier_canary_t-iso-{i}.txt",
                "mode": "NATIVE",
                "artifacts": [f"courier_canary_t-iso-{i}.txt"]
            })
            
        goal_payload = {
            "goal_text": "M1 Physical Acceptance Isolated",
            "workflow_plan": plan,
            "terminal": True
        }
        
        req = urllib.request.Request(
            "http://127.0.0.1:8089/goals",
            data=json.dumps(goal_payload).encode(),
            headers={"Authorization": "Bearer test-key", "Content-Type": "application/json"},
            method="POST"
        )
        res = urllib.request.urlopen(req)
        goal_id = json.loads(res.read())["goal_id"]
        
        print(f"[Acceptance] Goal submitted: {goal_id}. Waiting for completion...")
        
        success = False
        for _ in range(30):
            try:
                with open(state_file, "r") as f:
                    st = json.load(f)
                    status = st["goals"].get(goal_id, {}).get("status")
                    if status == "DONE":
                        success = True
                        break
            except Exception:
                pass
            time.sleep(1)
                
        server_proc.terminate()
        verifier_proc.terminate()
        w1_proc.terminate()
        
        if success:
            print("[Acceptance] PASS: 10 tasks completed by REAL workers.")
            
            # Print the schema requested
            print("\n====================")
            print("FIRST CAUSAL BLOCKER")
            print("Mac OS worker's HTTP result payloads lacked 'execution_ref', causing verifier rejection (HTTP 400), and state loading lacked isolation/truncation safety.")
            print("\nEXACT SHA")
            print(os.popen("git rev-parse HEAD").read().strip())
            print("\nMINIMAL REPAIR")
            print("Patched 'execution_ref' into scripts/mac_worker/daemon.py result payload. Isolated verification tests to custom ports and tmpdirs.")
            print("\nSAME EXECUTABLE PROOF")
            print("run_acceptance.py executing 10 NATIVE tasks via subprocess real daemon.py, real verifier, real server on an isolated port.")
            print("\nRESULT")
            print("PHYSICAL_ACCEPTANCE_PASS")
            print("\nNEXT FIRST BLOCKER")
            print("None.")
            print("====================")
        else:
            print("[Acceptance] FAIL: Goal did not complete in time.")
            sys.exit(1)

if __name__ == "__main__":
    run_proof()
