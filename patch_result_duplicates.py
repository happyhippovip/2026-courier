import re

with open("tests/test_result_duplicates.py", "r") as f:
    content = f.read()

content = content.replace('"execution_ref": "1"\n        }', '"execution_ref": "1",\n            "server_binding": server.app.SERVER_BINDING\n        }')

replacement = """
    import hashlib, json
    
    payload1 = {
        "task_id": task_id,
        "worker_id": "worker-1",
        "status": "SUCCESS",
        "artifacts": [{"path": "file.txt", "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}],
        "attempt_id": "1",
        "dispatch_id": "1",
        "execution_ref": "1",
        "goal_id": "goal-1",
        "run_id": "run-1",
        "runtime_identity": server.app.SERVER_BINDING
    }
    identity1 = {k: payload1.get(k) for k in ("goal_id", "task_id", "attempt_id", "dispatch_id", "execution_ref", "worker_id", "run_id", "status", "artifacts", "runtime_identity")}
    rid1 = "res-" + hashlib.sha256(json.dumps(identity1, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    payload1["result_id"] = rid1

    resp1 = client.post("/tasks/result", json=payload1, headers=headers)
    assert resp1.status_code == 200

    resp2 = client.post("/tasks/result", json=payload1, headers=headers)
    assert resp2.status_code == 200
    assert resp2.get_json()["status"] == "ACK_DUPLICATE"

    payload_contradictory = {
        "task_id": task_id,
        "worker_id": "worker-1",
        "status": "SUCCESS",
        "artifacts": [],
        "attempt_id": "1",
        "dispatch_id": "1",
        "execution_ref": "1",
        "goal_id": "goal-1",
        "run_id": "run-1",
        "runtime_identity": server.app.SERVER_BINDING
    }
    identity3 = {k: payload_contradictory.get(k) for k in ("goal_id", "task_id", "attempt_id", "dispatch_id", "execution_ref", "worker_id", "run_id", "status", "artifacts", "runtime_identity")}
    rid3 = "res-" + hashlib.sha256(json.dumps(identity3, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    payload_contradictory["result_id"] = rid3

    resp3 = client.post("/tasks/result", json=payload_contradictory, headers=headers)
    assert resp3.status_code == 409
    assert resp3.get_json()["status"] == "CONFLICT"
    assert resp3.get_json()["reason"] == "CONTRADICTORY_DUPLICATE"

    state = server.app.load_state()
    assert state["tasks"][task_id]["result"]["result_id"] == rid1

    payload_worker2 = dict(payload1)
    payload_worker2["worker_id"] = "worker-2"
    identity4 = {k: payload_worker2.get(k) for k in ("goal_id", "task_id", "attempt_id", "dispatch_id", "execution_ref", "worker_id", "run_id", "status", "artifacts", "runtime_identity")}
    rid4 = "res-" + hashlib.sha256(json.dumps(identity4, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    payload_worker2["result_id"] = rid4
    
    resp4 = client.post("/tasks/result", json=payload_worker2, headers=headers)
"""
content = re.sub(r'    payload1 = \{.*resp4 = client\.post\("/tasks/result", json=payload_worker2, headers=headers\)', replacement, content, flags=re.DOTALL)

with open("tests/test_result_duplicates.py", "w") as f:
    f.write(content)
