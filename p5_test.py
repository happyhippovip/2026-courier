import requests
import json
import os
import uuid

API_URL = os.environ.get('COURIER_SERVER', 'http://127.0.0.1:8080').rstrip('/')
API_KEY = "test-key-123" # No auth required or handled in mock? Wait, server auth is disabled in dev?
# Wait, server has @require_auth.
HEADERS = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}

goal_payload = {
    'goal_id': f"GOAL-P5-{uuid.uuid4().hex[:8].upper()}",
    'goal_text': json.dumps([{"target_agent": "windows", "instruction": "P5_TEST_TASK"}]),
    'terminal': False
}

print(requests.post(f"{API_URL}/goals", json=goal_payload, headers=HEADERS).json())
