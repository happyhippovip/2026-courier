#!/usr/bin/env python3
import json
import sys

def verify_task():
    try:
        with open("ops/ai/PILOT_DUMMY_TASK.json", "r") as f:
            goal = json.load(f)
            
        if "workflow_plan" not in goal or not goal["workflow_plan"]:
            print("FAILED: Missing or empty workflow_plan")
            sys.exit(1)
            
        task = goal["workflow_plan"][0]
        required_fields = ["task_id", "goal_id", "target_capability", "instruction", "status"]
        missing = [f for f in required_fields if f not in task]
        
        if missing:
            print(f"FAILED: Missing fields {missing}")
            sys.exit(1)
            
        if task["status"] != "QUEUED":
            print(f"FAILED: status should be QUEUED, got {task['status']}")
            sys.exit(1)
            
        print("PILOT TASK VERIFIED - SCHEMA MATCHES")
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_task()
