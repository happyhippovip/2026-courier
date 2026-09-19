def complete(http, worker_id, task_id, status="SUCCESS"):
    payload = {
        "worker_id": worker_id,
        "task_id": task_id,
        "status": status,
        "artifacts": [],
        "raw_result": {"status": status}
    }
    resp = http.post("/tasks/result", headers={"Authorization": "Bearer test-secret"}, json=payload)
    print("COMPLETE RESP:", resp.status_code, resp.get_data())
    assert resp.status_code == 200
