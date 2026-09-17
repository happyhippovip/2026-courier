#!/usr/bin/env python3
import os
import sys
import json
import uuid
import requests

API_URL = os.environ.get('COURIER_SERVER', 'http://127.0.0.1:8080').rstrip('/')
API_KEY = os.environ.get('COURIER_API_KEY', 'default_key')
HEADERS = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}

def submit_goal(goal_text: str):
    goal_id = f"GOAL-{uuid.uuid4().hex[:8].upper()}"
    task_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"
    
    # Courier internally creates TaskPackets, dependencies, routing, verification
    # Customer only submitted the single goal text
    goal_payload = {
        'goal_id': goal_id,
        'goal_text': goal_text,
        'workflow_plan': [
            {
                'task_id': task_id,
                'type': 'generic_decomposition',
                'capabilities': ['auto_plan', 'execute', 'verify'],
                'status': 'QUEUED',
                'target_agent': 'auto',
                'dependencies': [],
                'idempotency_key': task_id
            }
        ]
    }
    
    print(f"Submitting canonical GOAL: {goal_id}")
    print(f"Goal Text: {goal_text}")
    print(f"Internal TaskPackets automatically generated: {task_id}")
    
    try:
        res = requests.post(f"{API_URL}/goals", json=goal_payload, headers=HEADERS)
        if res.status_code == 200:
            print("Successfully submitted to Courier Central Server.")
        else:
            print(f"API Error (Mocked local): {res.status_code}")
            # Mock success for local architecture without server
            print("Writing to local goals directory for fallback processing...")
            os.makedirs('intakes', exist_ok=True)
            with open(f'intakes/{goal_id}.json', 'w') as f:
                json.dump(goal_payload, f, indent=2)
            print(f"Goal {goal_id} written locally.")
    except Exception as e:
        print(f"Could not connect to {API_URL}: {e}")
        print("Writing to local goals directory for fallback processing...")
        os.makedirs('intakes', exist_ok=True)
        with open(f'intakes/{goal_id}.json', 'w') as f:
            json.dump(goal_payload, f, indent=2)
        print(f"Goal {goal_id} written locally.")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 submit_goal.py '<your goal description>'")
        sys.exit(1)
        
    submit_goal(sys.argv[1])
