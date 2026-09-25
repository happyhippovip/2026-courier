import re
from pathlib import Path

p = Path("tests/test_server_integration_contract.py")
content = p.read_text()

# Find the def test_result_from_unauthorized_worker_fails_closed and replace it entirely
new_func = """def test_result_from_unauthorized_worker_fails_closed(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    from server.app import load_state, save_state
    
    st = load_state()
    st["tasks"]["t1"] = {
        "task_id": "t1",
        "status": "DISPATCHED",
        "worker_id": "MAC-01",
        "attempt_id": "a1"
    }
    st["workers"]["MAC-01"] = {"worker_id": "MAC-01", "current_task": "t1"}
    st["workers"]["MAC-02"] = {"worker_id": "MAC-02", "current_task": None}
    save_state(st)
    
    # Submit a result from a different worker (MAC-02)
    res = c.post("/tasks/result", headers=auth(), json={
        "task_id": "t1",
        "worker_id": "MAC-02",
        "status": "SUCCESS",
        "result_id": "res_t1",
        "artifacts": []
    })
    assert res.status_code == 403
    assert res.json["error"] == "WORKER_MISMATCH"
"""

content = re.sub(r'def test_result_from_unauthorized_worker_fails_closed.*', new_func, content, flags=re.DOTALL)
p.write_text(content)
