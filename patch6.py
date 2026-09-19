def verify(http, task_id):
    headers={"Authorization": "Bearer verifier-secret"}
    resp = http.post("/tasks/verify", headers=headers, json={"task_id": task_id, "verdict": "PASS"})
    print("VERIFY RESP:", resp.status_code, resp.get_data())
    assert resp.status_code == 200
