"""Manual live-server E2E smoke probe (NOT part of the automated suite).

Run directly against a local Courier server: ``python3 test_canary.py``.
Importing this module must have no side effects so bare ``pytest``
collection from the repo root stays clean.
"""
import requests

API = "http://127.0.0.1:8080"
HEADERS = {"Authorization": "Bearer dev-secret-key", "Content-Type": "application/json"}


def main():
    # 1. Register worker
    print("Registering worker...")
    res = requests.post(f"{API}/workers/register", headers=HEADERS, json={"worker_id": "test-canary-worker", "platform": "linux", "capabilities": ["linux"]})
    print(res.json())

    # 2. Submit multi-step goal
    print("Submitting goal...")
    goal_data = {
        "goal_text": "Test E2E",
        "workflow_plan": [
            {"target_agent": "linux", "instruction": "echo TASK_A", "task_id": "task-A"},
            {"target_agent": "linux", "instruction": "echo TASK_B", "task_id": "task-B"}
        ]
    }
    res = requests.post(f"{API}/goals", headers=HEADERS, json=goal_data)
    print(res.json())

    # 3. Heartbeat
    print("Heartbeat...")
    res = requests.post(f"{API}/workers/heartbeat", headers=HEADERS, json={"worker_id": "test-canary-worker"})
    print(res.json())

    # 4. Claim Task A
    print("Claiming task A...")
    res = requests.post(f"{API}/tasks/claim", headers=HEADERS, json={"worker_id": "test-canary-worker"})
    task_a = res.json().get("task")
    print(task_a)

    # 5. Submit Result A
    print("Submitting Result A...")
    res = requests.post(f"{API}/tasks/result", headers=HEADERS, json={"worker_id": "test-canary-worker", "task_id": "task-A", "status": "SUCCESS"})
    print(res.json())

    # 6. Check status to see if active
    print("Checking status...")
    res = requests.get(f"{API}/status", headers=HEADERS)
    print(res.json())

    # 7. Claim Task B
    print("Claiming task B...")
    res = requests.post(f"{API}/tasks/claim", headers=HEADERS, json={"worker_id": "test-canary-worker"})
    task_b = res.json().get("task")
    print(task_b)

    # 8. Submit Result B
    print("Submitting Result B...")
    res = requests.post(f"{API}/tasks/result", headers=HEADERS, json={"worker_id": "test-canary-worker", "task_id": "task-B", "status": "SUCCESS"})
    print(res.json())

    # 9. Verify duplicate protection
    print("Submitting Duplicate Result B...")
    res = requests.post(f"{API}/tasks/result", headers=HEADERS, json={"worker_id": "test-canary-worker", "task_id": "task-B", "status": "SUCCESS"})
    print(res.json())

    # 10. Check final status (Goal should be DONE)
    print("Checking final status...")
    res = requests.get(f"{API}/status", headers=HEADERS)
    print(res.json())


if __name__ == "__main__":
    main()
