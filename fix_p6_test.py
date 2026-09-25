from pathlib import Path
p = Path("tests/test_p6_economics.py")
content = p.read_text()

target = """    resp = client.post("/tasks/result", headers=auth(), json={
        "task_id": "T-P6-1",
        "worker_id": "W-P6",
        "status": "SUCCESS",
        "actual_cost": 6.00,
        "result_id": "res-123",
        "artifacts": []
    })"""
    
repl = """    payload = dict(task)
    payload.update({
        "status": "SUCCESS",
        "actual_cost": 6.00,
        "result_id": "res-123",
        "artifacts": [],
        "runtime_identity": "worker",
    })
    resp = client.post("/tasks/result", headers=auth(), json=payload)"""

content = content.replace(target, repl)
p.write_text(content)
