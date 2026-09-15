import json
import time
import subprocess
from pathlib import Path
import os
import sys
import hashlib

sys.path.append(str(Path(__file__).resolve().parent.parent))
from scripts.opportunity_queue import OpportunityQueue, Opportunity
from scripts.next_safe_work_router import NextSafeWorkRouter
from scripts.live_worker_registry import LiveWorkerRegistry, WorkerState, AvailabilityClass
from scripts.mac_result_consumer import consume_results

STATE_FILE = Path("events/runtime-state/CONTINUATION_STATE.json")
COURIER_DIR = Path(__file__).resolve().parent.parent

def load_state():
    if not STATE_FILE.exists():
        return {}
    with open(STATE_FILE, "r") as f:
        return json.load(f)
        
def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["UPDATED_AT"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    
    tmp = STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=4)
    tmp.replace(STATE_FILE)

# Capability Mapping
def map_action(action):
    supported = {"HEALTH_CHECK", "READ_FILE", "WRITE_FILE", "WRITE_PROOF", "RUN_TEST"}
    return action if action in supported else "UNSUPPORTED_CAPABILITY"

def select_next_task(queue, router):
    # Register/Refresh WINDOWS worker
    reg = router.registry
    record = reg.register_worker("WINDOWS", "WINDOWS_NATIVE", "WINDOWS", availability_class=AvailabilityClass.TEMPORARY_30_DAY, mutable_scope=[r"C:\Dev\Windows-AI-OS"])
    record.state = WorkerState.AVAILABLE.value
    reg._save_worker_record(record)
    
    res = router.evaluate_next_safe_work()
    recs = res.get("recommendations", {})
    
    for worker_id, rec in recs.items():
        if worker_id != "WINDOWS":
            continue
            
        action = rec.get("recommended_action", "")
        if action.startswith("DISPATCH_TASK_"):
            task_id = action.replace("DISPATCH_TASK_", "", 1)
            opp = queue.get_opportunity(task_id)
            if opp and opp.status == "READY":
                return opp, rec
    return None, None

def verify_proof(task_id):
    # Verify the proof file is created in Windows remote-proofs
    # Actually, the result JSON from Windows executor returns PROOF_WRITTEN in OUTPUT
    pass

def main():
    print("Starting Canonical MAC Continuous Controller...")
    
    # Ensure one active controller via simple PID file
    pid_file = COURIER_DIR / "events" / "runtime-state" / "controller.pid"
    if pid_file.exists():
        with open(pid_file) as f:
            old_pid = f.read().strip()
        # Verify if process is running
        if old_pid.isdigit():
            try:
                os.kill(int(old_pid), 0)
                print(f"Controller already running as PID {old_pid}")
                sys.exit(1)
            except OSError:
                pass
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))
        
    try:
        while True:
            state = load_state()
            queue = OpportunityQueue(repo_dir=COURIER_DIR)
            router = NextSafeWorkRouter(repo_dir=COURIER_DIR)
            
            # Check for orphaned running tasks in state
            # If we restarted and ACTIVE_TASK_COUNT == 1, we could check results.
            
            opp, rec = select_next_task(queue, router)
            if not opp:
                time.sleep(5)
                continue
                
            task_id = opp.opportunity_id
            print(f"--- Selected Opportunity: {task_id} ---")
            
            # Map action
            opp_action = opp.allowed_actions[0] if opp.allowed_actions else ""
            mapped_action = map_action(opp_action)
            
            if mapped_action == "UNSUPPORTED_CAPABILITY":
                print(f"Task {task_id} has unsupported action {opp_action}.")
                opp.status = "UNSUPPORTED"
                queue.save_opportunity(opp)
                state["LAST_RESULT"] = f"UNSUPPORTED: {opp_action}"
                save_state(state)
                continue
            
            payload = {
                "TASK_ID": task_id,
                "TARGET_HOST": "windows-ai",
                "PROJECT_PATH": "C:\\Dev\\Windows-AI-OS",
                "ACTION": mapped_action,
                "DESCRIPTION": opp.description,
                "Content": opp.description # For WRITE_PROOF
            }
            
            # Update state to active
            state["CURRENT_TASK_ID"] = task_id
            state["CURRENT_OPPORTUNITY"] = opp.description
            state["ACTIVE_CONTROLLER_COUNT"] = 1
            state["LAST_COMPLETED_TASK"] = None
            save_state(state)
            
            opp.status = "ACTIVE"
            queue.save_opportunity(opp)
            
            tmp_file = Path(f"/tmp/{task_id}.json")
            with open(tmp_file, "w") as f:
                json.dump(payload, f)
                
            # Dispatch
            res = subprocess.run(["python3", "scripts/mac_windows_dispatcher.py", str(tmp_file)], capture_output=True, text=True)
            if tmp_file.exists():
                tmp_file.unlink()
                
            # Parse result
            result_state = "FAILED"
            out_json = None
            for line in reversed(res.stdout.splitlines()):
                try:
                    parsed = json.loads(line)
                    if "STATE" in parsed:
                        result_state = parsed["STATE"]
                        if result_state == "RESULT_RECEIVED":
                            out_json = parsed
                        break
                except:
                    pass
            
            if result_state == "RESULT_RECEIVED" and out_json and out_json.get("STATUS") == "SUCCESS":
                print(f"Task {task_id} completed successfully.")
                state["LAST_RESULT"] = "SUCCESS"
                opp.status = "COMPLETED"
                queue.save_opportunity(opp)
                
                # Causal next step: Generate Task B
                if mapped_action == "WRITE_PROOF":
                    # Derive Task B
                    import uuid
                    task_b_id = f"task-b-{uuid.uuid4().hex[:6]}"
                    opp_b = Opportunity(
                        opportunity_id=task_b_id,
                        source="MAC_CONTINUOUS_CONTROLLER",
                        project="Courier",
                        objective_id="OBJ-CHAIN",
                        description=f"Follow-up proof after {task_id}",
                        priority=opp.priority + 1,
                        target_agent="WINDOWS",
                        allowed_actions=["WRITE_PROOF"],
                        allowed_scope=["C:\\Dev\\Windows-AI-OS"]
                    )
                    opp_b.status = "READY"
                    queue.add_opportunity(opp_b)
                    queue.save_opportunity(opp_b)
                    print(f"Generated causal Task B: {task_b_id}")
            else:
                print(f"Task {task_id} failed: {res.stderr} | {res.stdout}")
                state["LAST_RESULT"] = "FAILED"
                opp.status = "RETRYABLE"
                queue.save_opportunity(opp)
                
            state["LAST_COMPLETED_TASK"] = task_id
            state["CURRENT_TASK_ID"] = None
            state["CURRENT_OPPORTUNITY"] = None
            save_state(state)
            
            print("Cycle complete. Continuing...")
            time.sleep(2)
            
            # Since this is an integration proof test, if we did Task A and generated Task B, we will let it loop and pick up Task B!
            # The prompt says: "Run Task B through the same real pipeline."
            # After Task B succeeds, we will have proven it.

    finally:
        if pid_file.exists():
            pid_file.unlink()

if __name__ == "__main__":
    main()
