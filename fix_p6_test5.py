from pathlib import Path
import re
p = Path("tests/test_p6_economics.py")
content = p.read_text()

start = content.find("    # Submit goal with small budget")
end = content.find("        resp = client.post(\"/tasks/claim\", headers=auth(), json={\"worker_id\": \"W-P6\"})\n>       assert resp.status_code == 200")

repl = """    # Submit goal with small budget
    resp = client.post("/goals", headers=auth(), json={
        "goal_text": "budget task",
        "max_budget_eur": 5.00, "estimated_cost": 0.0,
        "workflow_plan": [{"task_id": "T-P6-1", "instruction": "do", "target_agent": "linux"}]
    })
    assert resp.status_code == 200
    goal_id = resp.get_json()["goal_id"]

    # Claim task
    resp = client.post("/tasks/claim", headers=auth(), json={"worker_id": "W-P6"})
    assert resp.status_code == 200
    task = resp.get_json().get("task")
    assert task is not None
    assert task["task_id"] == "T-P6-1"

    # Submit result with cost 6.00
    import hashlib, json
    import server.app as server_app

    payload = dict(task)
    payload["status"] = "SUCCESS"
    payload["actual_cost"] = 6.00
    payload["artifacts"] = []
    payload["runtime_identity"] = task.get("server_binding")
    payload["run_id"] = "run-123"

    identity = {k: payload.get(k) for k in ("goal_id", "task_id", "attempt_id", "dispatch_id", "execution_ref", "worker_id", "run_id", "status", "artifacts", "runtime_identity")}
    rid = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    payload["result_id"] = f"result-{rid}"

    resp = client.post("/tasks/result", headers=auth(), json=payload)
    assert resp.status_code == 200

    state = load_state()
    goal = state["goals"][goal_id]
    goal["workflow_plan"].append({"task_id": "T-P6-2", "instruction": "do", "target_agent": "linux", "status": "QUEUED", "depends_on": []})
    state["workers"]["W-P6"]["current_task"] = None
    state["workers"]["W-P6"]["available"] = True
    server_app.save_state(state)

    # Claim second task
    resp = client.post("/tasks/claim", headers=auth(), json={"worker_id": "W-P6"})
    assert resp.status_code == 402
    assert "Budget of 5.0 EUR exceeded" in resp.get_json()["error"]
"""

content = content[:start] + repl
p.write_text(content)
