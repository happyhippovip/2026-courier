"""Manual live-server retry probe (NOT part of the automated suite).

Run directly against a local Courier server: ``python3 test_retry.py``.
Importing this module must have no side effects so bare ``pytest``
collection from the repo root stays clean.
"""
import requests

API = "http://127.0.0.1:8080"
HEADERS = {"Authorization": "Bearer dev-secret-key-123", "Content-Type": "application/json"}


def main():
    requests.post(f"{API}/workers/register", headers=HEADERS, json={"worker_id": "test-worker", "platform": "linux", "capabilities": ["linux"]})
    goal_data = {
        "goal_text": "Test Retry",
        "workflow_plan": [{"target_agent": "linux", "instruction": "echo TASK_RETRY", "task_id": "task-retry"}]
    }
    requests.post(f"{API}/goals", headers=HEADERS, json=goal_data)

    # Claim 1
    res1 = requests.post(f"{API}/tasks/claim", headers=HEADERS, json={"worker_id": "test-worker"}).json()
    print("Claim 1:", res1["task"]["attempts"])
    # Fail 1
    requests.post(f"{API}/tasks/result", headers=HEADERS, json={"worker_id": "test-worker", "task_id": "task-retry", "status": "FAILED"})

    # Claim 2
    res2 = requests.post(f"{API}/tasks/claim", headers=HEADERS, json={"worker_id": "test-worker"}).json()
    print("Claim 2:", res2["task"]["attempts"])
    # Fail 2
    requests.post(f"{API}/tasks/result", headers=HEADERS, json={"worker_id": "test-worker", "task_id": "task-retry", "status": "FAILED"})

    # Claim 3
    res3 = requests.post(f"{API}/tasks/claim", headers=HEADERS, json={"worker_id": "test-worker"}).json()
    print("Claim 3:", res3["task"]["attempts"])
    # Fail 3
    requests.post(f"{API}/tasks/result", headers=HEADERS, json={"worker_id": "test-worker", "task_id": "task-retry", "status": "FAILED"})

    # Claim 4 (Should be None)
    res4 = requests.post(f"{API}/tasks/claim", headers=HEADERS, json={"worker_id": "test-worker"}).json()
    print("Claim 4:", res4.get("task"))

    # Status of goal
    print(requests.get(f"{API}/status", headers=HEADERS).json())


if __name__ == "__main__":
    main()
