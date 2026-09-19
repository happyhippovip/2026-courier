def claim(http, worker_id):
    resp = http.post("/tasks/claim", headers={"Authorization": "Bearer test-secret"}, json={"worker_id": worker_id})
    print(resp.json)
    return resp.get_json().get("task") if resp.status_code == 200 else None
