def verify(http, task_id):
    headers={"Authorization": "Bearer verifier-secret"}
    resp = http.post("/tasks/verify", headers=headers, json={"task_id": task_id, "verdict": "PASS", "verifier_id": "V1", "result_id": f"res-{task_id}"})
    print("VERIFY RESP:", resp.status_code, resp.get_data())
    assert resp.status_code == 200
