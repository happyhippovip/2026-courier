#!/usr/bin/env python3
import os
import sys
import json

def map_internal_to_customer_status(internal_state: str) -> str:
    state = internal_state.upper()
    if state in ['NEW', 'QUEUED', 'PENDING_DISPATCH']:
        return 'QUEUED'
    elif state in ['RUNNING', 'IN_PROGRESS', 'DISPATCHED_TO_EXTERNAL', 'EXECUTING']:
        return 'RUNNING'
    elif state in ['WAITING', 'WAITING_FOR_CHIEF_COMMAND', 'WAIT_FOR_GITHUB_PR', 'BLOCKED']:
        return 'WAITING'
    elif state in ['NEEDS_APPROVAL', 'HUMAN_REVIEW_REQUIRED_ON_PR', 'HUMAN_GATE_REQUIRED']:
        return 'NEEDS_APPROVAL'
    elif state in ['DONE', 'COMPLETED', 'SUCCESS', 'VERIFIED']:
        return 'DONE'
    elif state in ['FAILED', 'ERROR', 'SYSTEM_FAILURE']:
        return 'FAILED'
    return 'WAITING' # Safe fallback

def get_customer_view(task_id: str, is_admin: bool = False):
    state_file = 'central_state.json'
    if not os.path.exists(state_file):
        return {"error": "No tasks found."}
        
    with open(state_file, 'r') as f:
        state = json.load(f)
        
    tasks = state.get("tasks", {})
    if task_id not in tasks:
        return {"error": "Task not found."}
        
    internal_task = tasks[task_id]
    
    # Base customer view
    customer_view = {
        "task_id": internal_task.get("task_id"),
        "customer_reference": internal_task.get("customer_reference", "N/A"),
        "status": map_internal_to_customer_status(internal_task.get("state", "QUEUED"))
    }
    
    # Only expose internal details if admin view
    if is_admin:
        customer_view["_internal_state"] = internal_task.get("state")
        customer_view["_worker_id"] = internal_task.get("worker_id")
        customer_view["_dispatch_ref"] = internal_task.get("dispatch_ref")
        customer_view["_execution_ref"] = internal_task.get("execution_ref")
        customer_view["_real_wall"] = internal_task.get("real_wall")
        
    return customer_view

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 customer_status_view.py <task_id> [--admin]")
        sys.exit(1)
        
    task_id = sys.argv[1]
    is_admin = len(sys.argv) > 2 and sys.argv[2] == "--admin"
    
    view = get_customer_view(task_id, is_admin)
    print(json.dumps(view, indent=2))

if __name__ == '__main__':
    main()
