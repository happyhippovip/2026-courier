import importlib.util
import json
from pathlib import Path

import pytest

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mac_worker" / "daemon.py"


class StopLoop(BaseException):
    """Ends daemon.loop(); BaseException passes through its `except Exception`."""


def load_daemon(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("mac_worker_daemon_under_test", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    (tmp_path / "state").mkdir()
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(daemon, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(daemon, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(daemon, "load_config", lambda: {
        "COURIER_SERVER": "http://courier.invalid", "WORKER_ID": "MAC-01", "POLL_INTERVAL_SECONDS": 0,
        "COURIER_API_KEY": "dummy-test-key-not-real",
    })
    monkeypatch.setattr(daemon.time, "sleep", lambda seconds: None)
    return daemon


class FakeServer:
    def __init__(self, claims=(), results=(), max_calls=40):
        self.claims = list(claims)
        self.results = list(results)
        self.max_calls = max_calls
        self.calls = []

    def __call__(self, config, endpoint, data):
        self.calls.append((endpoint, json.loads(json.dumps(data))))
        if len(self.calls) > self.max_calls:
            raise StopLoop()
        if endpoint == "/tasks/claim":
            return ({"task": self.claims.pop(0)} if self.claims else {"task": None}), None
        if endpoint == "/tasks/result":
            if not self.results:
                raise StopLoop()
            return self.results.pop(0)
        return {"status": "OK"}, None

    def posted(self, endpoint):
        return [data for called, data in self.calls if called == endpoint]


def task(**extra):
    packet = {
        "task_id": "task-1", "goal_id": "goal-1", "attempt_id": "task-1:attempt:1",
        "dispatch_id": "dispatch-abc", "worker_id": "MAC-01", "mode": "NATIVE",
        "instruction": "echo hi", "artifacts": [],
    }
    packet.update(extra)
    return packet


def run(daemon, monkeypatch, server, executions):
    def execute(packet, config):
        executions.append(packet["task_id"])
        return {"status": "FAILED", "stderr": "bounded test run", "execution_mode": "NATIVE"}

    monkeypatch.setattr(daemon, "http_post", server)
    monkeypatch.setattr(daemon, "run_native", execute)
    monkeypatch.setattr(daemon, "run_agy", execute)
    with pytest.raises(StopLoop):
        daemon.loop()


def state_file(daemon):
    return daemon.STATE_DIR / "current_task.json"


def test_restart_after_started_execution_does_not_execute_again(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    # Legacy state files carry no phase; the old daemon wrote them right before executing.
    for persisted in (task(), task(worker_phase="STARTED"), task(worker_phase="garbage")):
        state_file(daemon).write_text(json.dumps(persisted))
        server, executions = FakeServer(max_calls=6), []

        run(daemon, monkeypatch, server, executions)

        assert executions == []
        assert server.posted("/tasks/result") == []
        # Existing Courier recovery path: registering without the task makes the
        # server quarantine it as HUMAN_REQUIRED instead of replaying it.
        assert server.posted("/workers/register")[0]["current_task"] is None
        assert not state_file(daemon).exists()


def test_restart_with_stored_result_resends_it_without_recomputing(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    stored = {"task_id": "task-1", "dispatch_id": "dispatch-abc", "result_id": "result-fixed",
              "run_id": "run-fixed", "status": "FAILED", "artifacts": []}
    state_file(daemon).write_text(json.dumps(task(worker_phase="RESULT_READY", result_payload=stored)))
    server, executions = FakeServer(results=[({"status": "ACK_RESULT_RECEIVED"}, None)]), []

    run(daemon, monkeypatch, server, executions)

    assert executions == []
    assert server.posted("/tasks/result") == [stored]
    assert "current_task" not in server.posted("/workers/register")[0]
    assert not state_file(daemon).exists()


def test_claimed_but_not_started_task_runs_once_after_restart(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    state_file(daemon).write_text(json.dumps(task(worker_phase="CLAIMED")))
    server, executions = FakeServer(results=[({"status": "ACK_RESULT_RECEIVED"}, None)]), []

    run(daemon, monkeypatch, server, executions)

    assert executions == ["task-1"]
    assert len(server.posted("/tasks/result")) == 1
    assert "current_task" not in server.posted("/workers/register")[0]


def test_normal_claim_executes_once_and_posts_bound_result(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    server = FakeServer(claims=[task()], results=[({"status": "ACK_RESULT_RECEIVED"}, None)])
    executions = []

    run(daemon, monkeypatch, server, executions)

    assert executions == ["task-1"]
    [posted] = server.posted("/tasks/result")
    assert (posted["task_id"], posted["dispatch_id"], posted["attempt_id"]) == (
        "task-1", "dispatch-abc", "task-1:attempt:1")
    assert not state_file(daemon).exists()


def test_transport_errors_and_5xx_are_retried_with_identical_payload(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    server = FakeServer(claims=[task()], results=[
        (None, "timed out"),
        (None, "HTTP Error 502: Bad Gateway"),
        ({"status": "ACK_RESULT_RECEIVED"}, None),
    ])
    executions = []

    run(daemon, monkeypatch, server, executions)

    posts = server.posted("/tasks/result")
    assert len(posts) == 3
    assert posts[0] == posts[1] == posts[2]
    assert executions == ["task-1"]
    assert not state_file(daemon).exists()


def test_permanent_4xx_is_not_retried_and_result_is_kept_as_evidence(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    server = FakeServer(claims=[task()], results=[(None, 'HTTP Error 409: {"error": "Task is not awaiting a result"}')])
    executions = []

    run(daemon, monkeypatch, server, executions)

    assert len(server.posted("/tasks/result")) == 1
    assert executions == ["task-1"]
    assert not state_file(daemon).exists()
    [rejected] = list(daemon.STATE_DIR.glob("rejected_result_*.json"))
    assert json.loads(rejected.read_text())["result_payload"] == server.posted("/tasks/result")[0]


def test_undeliverable_result_is_kept_and_never_recomputed(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    server = FakeServer(claims=[task()], results=[(None, "connection refused")] * 12)
    executions = []

    run(daemon, monkeypatch, server, executions)

    assert executions == ["task-1"]
    assert len(server.posted("/tasks/claim")) == 1
    persisted = json.loads(state_file(daemon).read_text())
    assert persisted["worker_phase"] == "RESULT_READY"
    assert persisted["result_payload"] == server.posted("/tasks/result")[0]


def test_exception_during_execution_is_not_retried_in_process(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    server = FakeServer(claims=[task()], max_calls=8)
    executions = []

    def crash(packet, config):
        executions.append(packet["task_id"])
        raise RuntimeError("worker crashed mid-execution")

    monkeypatch.setattr(daemon, "http_post", server)
    monkeypatch.setattr(daemon, "run_native", crash)
    with pytest.raises(StopLoop):
        daemon.loop()

    assert executions == ["task-1"]
    assert server.posted("/tasks/result") == []
    assert server.posted("/workers/register")[-1]["current_task"] is None


def test_released_task_is_quarantined_by_courier_server_not_replayed(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", "test-secret")
    monkeypatch.setenv("COURIER_VERIFIER_API_KEY", "verifier-secret")
    server_app = importlib.import_module("server.app")
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "central.json"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    http = server_app.app.test_client()
    headers = {"Authorization": "Bearer test-secret"}
    http.post("/workers/register", headers=headers,
              json={"worker_id": "MAC-01", "platform": "macos", "capabilities": ["macos"]})
    http.post("/goals", headers=headers, json={"goal_text": "one effect", "workflow_plan": [
        {"task_id": "task-1", "target_agent": "mac", "artifacts": ["effect.txt"]}]})
    claimed = http.post("/tasks/claim", headers=headers, json={"worker_id": "MAC-01"}).get_json()["task"]

    daemon = load_daemon(tmp_path, monkeypatch)
    state_file(daemon).write_text(json.dumps(dict(claimed, worker_phase="STARTED")))
    executions, calls = [], []

    def via_server(config, endpoint, data):
        calls.append(endpoint)
        if len(calls) > 6:
            raise StopLoop()
        response = http.post(endpoint, headers=headers, json=data)
        return (response.get_json(), None) if response.status_code < 400 else (None, f"HTTP Error {response.status_code}: x")

    monkeypatch.setattr(daemon, "http_post", via_server)
    monkeypatch.setattr(daemon, "run_native", lambda packet, config: executions.append(packet) or {})
    monkeypatch.setattr(daemon, "run_agy", lambda packet, config: executions.append(packet) or {})
    with pytest.raises(StopLoop):
        daemon.loop()

    central = server_app.load_state()
    assert executions == []
    assert central["tasks"]["task-1"]["status"] == "HUMAN_REQUIRED"
    assert central["tasks"]["task-1"]["recovery_reason"] == "WORKER_RESTARTED_AND_LOST_STATE"
    assert central["goals"][claimed["goal_id"]]["status"] == "BLOCKED"
