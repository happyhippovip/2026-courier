#!/usr/bin/env python3
import os, sys, json, time
from datetime import datetime

STATE_FILE = "task_canary_state.json"
ARTIFACT_FILE = "artifact.txt"

def write_state(data):
    data["updated_at"] = datetime.now().isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(data, f, indent=2)

def read_state():
    if not os.path.exists(STATE_FILE):
        return {
            "agent_id": "none",
            "slot_id": "none",
            "task_id": "canary-task",
            "scope": "test_scope",
            "state": "READY",
            "last_confirmed_step": None,
            "last_result": None,
            "proof_ref": ARTIFACT_FILE,
            "next_action": "run_A",
            "expected_proof": "artifact containing A and B",
            "external_effect_state": None,
            "updated_at": ""
        }
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def run_part_a(state):
    print("[Worker] Executing Part A: Appending 'A' to artifact...")
    with open(ARTIFACT_FILE, "a") as f:
        f.write("A\n")
    
    state["agent_id"] = "muse-agent-01"
    state["slot_id"] = "MUSE-01"
    state["last_confirmed_step"] = "A"
    state["external_effect_state"] = "A_done"
    state["last_result"] = "Success A"
    state["next_action"] = "run_B"
    state["state"] = "RUNNING"
    write_state(state)
    print("[Worker] State saved. Simulating CRASH (e.g. PROVIDER_LIMIT/Timeout)...")
    sys.exit(1)

def run_part_b(state):
    print("[Worker] Executing Part B: Appending 'B' to artifact...")
    with open(ARTIFACT_FILE, "a") as f:
        f.write("B\n")
    
    state["agent_id"] = "muse-agent-02"
    state["slot_id"] = "MUSE-02"
    state["last_confirmed_step"] = "B"
    state["external_effect_state"] = "B_done"
    state["last_result"] = "Success B"
    state["next_action"] = "verify"
    state["state"] = "DONE"
    write_state(state)
    print("[Worker] Part B complete. Exiting cleanly.")

def worker_main():
    state = read_state()
    if state["next_action"] == "run_A":
        run_part_a(state)
    elif state["next_action"] == "run_B":
        run_part_b(state)

def supervisor_recovery_check():
    print("\n[Supervisor] Worker disappeared. Running RECOVERY CHECK...")
    state = read_state()
    
    has_proof = os.path.exists(state['proof_ref']) if state.get('proof_ref') else False
    
    print("1. Task-State:", state.get('state'))
    print(f"2. Proof: {state.get('proof_ref')} (exists: {has_proof})")
    print(f"3. External Effect State: {state.get('external_effect_state')}")
    print(f"4. Worker/Session Check: Slot {state.get('slot_id')} crashed.")
    
    # 5. Bestimmen:
    if state.get("state") == "DONE":
        decision = "DONE"
    elif state.get("state") == "BLOCKED":
        decision = "BLOCKED"
    elif not state.get("next_action"):
        decision = "WAIT"
    elif state.get("next_action") == "verify" and has_proof:
        decision = "VERIFY_ONLY"
    elif state.get("next_action") and state.get("slot_id") == "MUSE-01":
        # Simulate that if the SAME worker is somehow just disconnected but session alive, we would RESUME
        # But here it crashed, so we hand over.
        decision = "REDISPATCH"
    else:
        decision = "RESUME"
        
    print(f"-> Decision: {decision} (next_action = {state.get('next_action')})")
    return decision

def main():
    print("=== COURIER CONTINUITY / RESUME CANARY ===")
    if os.path.exists(STATE_FILE): os.remove(STATE_FILE)
    if os.path.exists(ARTIFACT_FILE): os.remove(ARTIFACT_FILE)
    
    print("\n--- Spawning Worker 1 ---")
    ret = os.system(f"python3 {__file__} --worker")
    
    if ret != 0:
        decision = supervisor_recovery_check()
        if decision == "REDISPATCH":
            print("\n--- Spawning Worker 2 (Recovery) ---")
            os.system(f"python3 {__file__} --worker")
            
    print("\n--- Verifying Results ---")
    if os.path.exists(ARTIFACT_FILE):
        with open(ARTIFACT_FILE, "r") as f:
            content = f.read()
        print(f"Artifact Content:\n{content.strip()}")
        if content == "A\nB\n":
            print(">>> PROOF PASS: No double execution. State resumed cleanly. <<<")

if __name__ == "__main__":
    if "--worker" in sys.argv:
        worker_main()
    else:
        main()
