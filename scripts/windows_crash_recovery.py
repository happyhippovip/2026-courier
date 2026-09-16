#!/usr/bin/env python3
import json
import os
import time

def recover_worker(worker_state_file='worker_state.json'):
    print("Initiating Windows Worker Crash Recovery...")
    
    if not os.path.exists(worker_state_file):
        print("No worker state found. Nothing to recover.")
        return
        
    with open(worker_state_file, 'r') as f:
        wstate = json.load(f)
        
    current_task = wstate.get('current_task')
    if not current_task:
        print("Worker crashed while idle. No recovery needed.")
        return
        
    task_id = current_task.get('task_id')
    execution_ref = current_task.get('execution_ref')
    last_known_phase = current_task.get('phase', 'UNKNOWN')
    
    print(f"Recovering execution {execution_ref} for task {task_id}")
    print(f"Last known phase before crash: {last_known_phase}")
    
    # 1. crash before external effect
    if last_known_phase == 'PRE_EFFECT':
        print("Crash occurred before any external effects. Safe to blindly re-execute.")
        print("Incrementing attempt_id and re-queueing.")
        
    # 2. crash after artifact creation (but no external network effect)
    elif last_known_phase == 'ARTIFACT_CREATED':
        print("Crash occurred after local artifact creation. Artifacts persist.")
        print("Resuming execution using existing artifact (no blind duplicate effort).")
        
    # 3. crash after external effect but before result post
    elif last_known_phase == 'POST_EXTERNAL_EFFECT':
        print("Crash occurred after external effect (ambiguous state).")
        print("AMBIGUOUS_EFFECT_FAIL_CLOSED: Failing the task to prevent duplicate external side-effect.")
        print("Human Gate or deterministic reconciliation required.")
        
    # 4. crash after result post but before acknowledgement
    elif last_known_phase == 'POST_RESULT':
        print("Crash occurred after result was posted to server but before ack.")
        print("Checking server for reconciled state...")
        print("Server has result. Acknowledging and marking DONE locally.")
        
    else:
        print("Unknown phase. Failing closed to prevent unsafe re-execution.")
        
    # Cleanup orphaned PIDs if any
    owned_pids = wstate.get('owned_pids', [])
    if owned_pids:
        print(f"Cleaning up orphaned processes from crash: {owned_pids}")
        # Process kill logic omitted for simulation
        
    # Clear worker state
    wstate['current_task'] = None
    wstate['owned_pids'] = []
    
    with open(worker_state_file, 'w') as f:
        json.dump(wstate, f, indent=2)

if __name__ == '__main__':
    # Setup mock crashes and recover
    for phase in ['PRE_EFFECT', 'ARTIFACT_CREATED', 'POST_EXTERNAL_EFFECT', 'POST_RESULT']:
        print(f"\n--- Simulating crash in phase: {phase} ---")
        mock_state = {
            "current_task": {
                "task_id": "WF-CANARY-STEP-1",
                "execution_ref": "exec_WIN_01_WF-CANARY-STEP-1",
                "attempt_id": 1,
                "phase": phase
            },
            "owned_pids": [12345]
        }
        with open('worker_state.json', 'w') as f:
            json.dump(mock_state, f)
            
        recover_worker()
