"""Resume(retry) must drop the superseded attempt's stored result so a
byte-identical replay cannot ACK as a duplicate. Portable: tests the
checkout it runs in (repo root derived from this file)."""
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_server(tmp_path, monkeypatch):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    monkeypatch.setenv("COURIER_API_KEY", "test-secret")
    monkeypatch.setenv("COURIER_VERIFIER_API_KEY", "verifier-secret")
    monkeypatch.setenv("COURIER_STATE_FILE", str(tmp_path / "central.json"))
    monkeypatch.setenv("COURIER_ARTIFACT_DIR", str(tmp_path / "artifact-store"))
    spec = importlib.util.spec_from_file_location(
        f"server_app_resume_{tmp_path.name}", ROOT / "server" / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WORKER = {"Authorization": "Bearer test-secret"}


def failed_result(task):
    return {f: task[f] for f in (
        "goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id")} | {
        "run_id": "run-1", "result_id": f"res-{task['attempt_id']}",
        "status": "FAILED",
        "artifacts": [{"path": "bounded.txt", "sha256": "a" * 64}]}


def test_resume_retry_drops_superseded_result(tmp_path, monkeypatch):
    srv = load_server(tmp_path, monkeypatch)
    http = srv.app.test_client()
    assert http.post("/workers/register", headers=WORKER, json={
        "worker_id": "MAC-01", "platform": "mac",
        "capabilities": ["macos"]}).status_code == 200
    http.post("/goals", headers=WORKER, json={
        "goal_text": "bounded", "workflow_plan": [{
            "task_id": "task-1", "target_agent": "mac",
            "instruction": "create bounded.txt",
            "artifacts": ["bounded.txt"]}]})
    last = None
    for _ in range(3):
        task = http.post("/tasks/claim", headers=WORKER,
                         json={"worker_id": "MAC-01"}).get_json()["task"]
        last = failed_result(task)
        assert http.post(
            "/tasks/result", headers=WORKER, json=last).status_code == 200
    assert srv.load_state()["tasks"]["task-1"]["status"] == "FAILED_TERMINAL"
    assert http.post("/tasks/task-1/resume", headers=WORKER,
                     json={"action": "retry"}).status_code == 200
    assert srv.load_state()["tasks"]["task-1"].get("result") in (None, {})
    replay = http.post("/tasks/result", headers=WORKER, json=last)
    assert replay.status_code in (400, 409)
    assert replay.get_json().get("status") != "ACK_DUPLICATE"
