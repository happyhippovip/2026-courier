#!/usr/bin/env python3
import json
import os
import psutil
import time

def check_task_health():
    # Canonical state
    state_file = '../central_state.json'
    worker_state_file = 'worker_state.json'
    
    # 1. Load canonical tasks
    valid_task_ids = set()
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            state = json.load(f)
            for goal_id, goal_data in state.get('goals', {}).items():
                for t in goal_data.get('workflow_plan', []):
                    if t.get('status') in ['RUNNING', 'WAITING_PROVIDER', 'WAITING']:
                        valid_task_ids.add(t.get('task_id'))
                        
    # 2. Check UI handles (mock representation of UI handles)
    # A STALE_UI_HANDLE is one where there is a UI state but no backing task in central_state
    # and no running PIDs.
    ui_handles = ['WF-CANARY-STEP-1', 'GHOST-TASK-99']
    
    for handle in ui_handles:
        if handle not in valid_task_ids:
            print(f"[STALE_UI_HANDLE] UI handle {handle} found but no canonical backend task. Removing UI handle only.")
            # In a real system, we would broadcast a WebSocket event or remove it from the dashboard DB.
            pass
            
    # 3. Check orphaned processes
    # An orphaned execution is one where the worker state claims a task/PID, 
    # but the heartbeat has expired or the canonical owner is invalid.
    if os.path.exists(worker_state_file):
        with open(worker_state_file, 'r') as f:
            wstate = json.load(f)
            
        current_task = wstate.get('current_task')
        owned_pids = wstate.get('owned_pids', [])
        last_heartbeat = wstate.get('last_heartbeat', 0)
        
        if current_task:
            task_id = current_task.get('task_id')
            
            # Simulated Heartbeat logic: if > 300 seconds stale
            heartbeat_stale = (time.time() - last_heartbeat) > 300 if last_heartbeat else False
            canonical_missing = task_id not in valid_task_ids
            
            if heartbeat_stale or canonical_missing:
                print(f"[ORPHANED_EXECUTION] Task {task_id} is stale or invalid.")
                for pid in list(owned_pids):
                    try:
                        p = psutil.Process(pid)
                        print(f"Terminating orphaned process tree (PID: {pid}) regardless of name...")
                        for child in p.children(recursive=True):
                            child.terminate()
                        p.terminate()
                    except psutil.NoSuchProcess:
                        pass
                
                # Release ownership and mark cleanup
                wstate['current_task'] = None
                wstate['owned_pids'] = []
                wstate['cleanup_evidence'] = f"Cleaned orphaned task {task_id} at {time.time()}"
                
                with open(worker_state_file, 'w') as f:
                    json.dump(wstate, f, indent=2)
            else:
                print(f"[VALID_RUNNING_EXECUTION] Task {task_id} is healthy and running. Do not terminate.")
                
if __name__ == '__main__':
    check_task_health()
