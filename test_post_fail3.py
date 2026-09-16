import requests, json, uuid
payload = {
    "worker_id": "MAC-01",
    "goal_id": "goal-acf9676d",
    "task_id": "task_crash_0fba24f8",
    "dispatch_id": "dispatch-27731c9cb6564cb7a65c579fd47dd712",
    "attempt_id": "task_crash_0fba24f8:attempt:2",
    "run_id": str(uuid.uuid4()),
    "result_id": str(uuid.uuid4()),
    "status": "FAILED",
    "stderr": "S02 Circuit Breaker: Task crashed 3 times.",
    "execution_mode": "CIRCUIT_BREAKER",
    "artifacts": [],
    "raw_result": {"status": "FAILED", "reason": "CRASH_LOOP"}
}
headers = {"Authorization": "Bearer prod-secret-12345", "Content-Type": "application/json"}
res = requests.post("http://localhost:8080/tasks/result", json=payload, headers=headers)
print(res.status_code, res.text)
