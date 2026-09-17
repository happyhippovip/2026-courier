#!/usr/bin/env python3
import os
import sys
import json
import uuid
import requests
import keyring
import argparse

API_URL = os.environ.get('COURIER_SERVER', 'http://127.0.0.1:8080').rstrip('/')
API_KEY = os.environ.get('COURIER_API_KEY') or keyring.get_password("courier_worker", "COURIER_API_KEY")
HEADERS = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}

def submit_goal(goal_text: str = None, json_file: str = None):
    goal_id = f"GOAL-{uuid.uuid4().hex[:8].upper()}"
    
    if json_file:
        with open(json_file, 'r') as f:
            goal_payload = json.load(f)
        if 'goal_id' not in goal_payload:
            goal_payload['goal_id'] = goal_id
        else:
            goal_id = goal_payload['goal_id']
        print(f"Submitting explicit JSON workflow from {json_file}...")
    else:
        goal_payload = {
            'goal_id': goal_id,
            'goal_text': goal_text
        }
        print(f"Submitting canonical GOAL: {goal_id}")
        print(f"Goal Text: {goal_text}")
    
    try:
        res = requests.post(f"{API_URL}/goals", json=goal_payload, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            print("Successfully submitted to Courier Central Server.")
        else:
            print(f"API Error: {res.status_code}")
            print(res.text)
    except Exception as e:
        print(f"Could not connect to {API_URL}: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Submit a goal to Courier")
    parser.add_argument('--file', help="Path to JSON file containing full goal payload (including workflow_plan)")
    parser.add_argument('goal_text', nargs='?', help="Goal text to formulate plan for")
    
    args = parser.parse_args()
    
    if not args.file and not args.goal_text:
        parser.print_help()
        sys.exit(1)
        
    submit_goal(goal_text=args.goal_text, json_file=args.file)
