"""Goal-intake guards: submit_goal validates plan shape before persisting."""
from server import app as server_app


def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    return server_app.app.test_client()


def auth():
    return {"Authorization": "Bearer test-secret"}


def submit(http, plan):
    return http.post("/goals", headers=auth(),
                     json={"goal_text": "g", "workflow_plan": plan})


def test_non_list_workflow_plan_rejected(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)
    resp = http.post("/goals", headers=auth(),
                     json={"goal_text": "g", "workflow_plan": "not-a-list"})
    assert resp.status_code == 400


def test_empty_workflow_plan_rejected(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)
    assert submit(http, []).status_code == 400


def test_duplicate_task_id_within_plan_rejected(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)
    plan = [
        {"task_id": "dup-1", "target_agent": "mac", "instruction": "a"},
        {"task_id": "dup-1", "target_agent": "mac", "instruction": "b"},
    ]
    assert submit(http, plan).status_code == 400


def test_duplicate_task_id_across_claim_rejected(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)
    http.post("/workers/register", headers=auth(),
              json={"worker_id": "MAC-01", "platform": "mac",
                    "capabilities": ["macos"]})
    plan = [{"task_id": "dup-2", "target_agent": "mac", "instruction": "a",
             "artifacts": []}]
    assert submit(http, plan).status_code == 200
    claimed = http.post("/tasks/claim", headers=auth(),
                        json={"worker_id": "MAC-01"})
    assert claimed.status_code == 200
    assert submit(http, plan).status_code == 400


def test_agent_normalization(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)
    plan = [{"task_id": "n-1", "target_agent": "antigravity", "instruction": "a"}]
    resp = submit(http, plan)
    assert resp.status_code == 200
    goal_id = resp.get_json()["goal_id"]
    state = server_app.load_state()
    steps = state["goals"][goal_id]["workflow_plan"]
    assert steps and steps[0]["target_agent"] == "mac"


def test_non_string_instruction_rejected(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)
    plan = [{"task_id": "s-1", "target_agent": "mac", "instruction": {"x": 1}}]
    assert submit(http, plan).status_code == 400
