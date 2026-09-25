from pathlib import Path
p = Path("tests/test_p6_economics.py")
content = p.read_text()

start = content.find("    # Submit result with cost 6.00")
end = content.find("    assert resp.status_code == 200\n") + len("    assert resp.status_code == 200\n")

repl = """    # Submit result with cost 6.00
    import hashlib, json
    import server.app as server_app
    
    payload = dict(task)
    payload["status"] = "SUCCESS"
    payload["actual_cost"] = 6.00
    payload["artifacts"] = []
    payload["runtime_identity"] = server_app.SERVER_BINDING
    
    identity = {k: payload.get(k) for k in ("goal_id", "task_id", "attempt_id", "dispatch_id", "execution_ref", "worker_id", "run_id", "status", "artifacts", "runtime_identity")}
    rid = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    payload["result_id"] = f"result-{rid}"
    
    resp = client.post("/tasks/result", headers=auth(), json=payload)
    assert resp.status_code == 200
"""

content = content[:start] + repl + content[end:]
p.write_text(content)
