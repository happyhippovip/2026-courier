#!/usr/bin/env python3
import json
import os
import subprocess
import time
import psutil
from windows_worker import WindowsPrimaryWorker

def trigger_account_switch(worker, new_account):
    print(">>> CUSTOMER TRIGGERED: SWITCH ACCOUNT / PROVIDER")
    
    # 1. checkpoint active work
    if worker.current_task:
        task_id = worker.current_task['task_id']
        print(f"Checkpointing active work for task {task_id}...")
        
        # 2. transition to WAITING_PROVIDER (NOT FAILED, NOT DONE)
        # Update central state
        state_file = '../central_state.json'
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            # Find the active task and mark WAITING_PROVIDER
            for goal_id, goal_data in state.get('goals', {}).items():
                for t in goal_data.get('workflow_plan', []):
                    if t.get('task_id') == task_id:
                        t['status'] = 'WAITING_PROVIDER'
                        t['provider_failure_reason'] = 'Account switch initiated by user'
            
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        print(f"Transitioned task {task_id} to WAITING_PROVIDER.")
    
    # 3. close unnecessary temporary processes
    # 5. preserve branch/dirty edits (we do not run git checkout or git reset here)
    print("Closing unnecessary temporary processes while preserving branch/dirty edits...")
    
    for pid in list(worker.owned_pids):
        try:
            p = psutil.Process(pid)
            for child in p.children(recursive=True):
                child.terminate()
            p.terminate()
        except psutil.NoSuchProcess:
            pass
    worker.owned_pids.clear()
    
    # 4. preserve task queue (by not clearing the central state)
    print("Task queue preserved.")
    
    # 6. accept new provider/account
    print(f"Accepting new provider/account: {new_account}")
    
    session_file = 'account_session.json'
    with open(session_file, 'w') as f:
        json.dump({"active_account": new_account}, f)
        
    # 7. resume same unfinished item
    print("Resuming unfinished item...")
    if worker.current_task:
        task_id = worker.current_task['task_id']
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state = json.load(f)
            for goal_id, goal_data in state.get('goals', {}).items():
                for t in goal_data.get('workflow_plan', []):
                    if t.get('task_id') == task_id:
                        t['status'] = 'RUNNING'
            
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        print(f"Resumed active item: {task_id}")
    
    # 8. continue rest of queue (queue is untouched)
    print("Queue ready to continue.")

if __name__ == '__main__':
    # Setup test
    worker = WindowsPrimaryWorker()
    worker.claim_task({"task_id": "WF-CANARY-STEP-1"})
    
    proc = subprocess.Popen(["ping", "127.0.0.1", "-n", "10"], shell=False)
    worker.owned_pids.add(proc.pid)
    worker.save_state()
    
    trigger_account_switch(worker, "NEW_ENTERPRISE_ACCOUNT")
