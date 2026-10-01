"""Mac worker recovery against the real server contract (no live Mac)."""
import hashlib
import importlib
import json

import pytest

from test_mac_worker_recovery import StopLoop, load_daemon, state_file


def central(tmp_path, monkeypatch, artifacts=("effect.txt",)):
    monkeypatch.setenv("COURIER_API_KEY", "test-secret")
    monkeypatch.setenv("COURIER_VERIFIER_API_KEY", "verifier-secret")
    srv = importlib.import_module("server.app")
    monkeypatch.setattr(srv, "STATE_FILE", str(tmp_path / "central.json"))
    monkeypatch.setattr(srv, "API_KEY", "test-secret")
    http = srv.app.test_client()
    headers = {"Authorization": "Bearer test-secret"}
    http.post("/workers/register", headers=headers,
              json={"worker_id": "MAC-01", "platform": "macos", "capabilities": ["macos"]})
    http.post("/goals", headers=headers, json={"goal_text": "g", "workflow_plan": [
        {"task_id": "task-1", "target_agent": "mac", "artifacts": list(artifacts)}]})
    return srv, http, headers


class Bridge:
    """Routes daemon.http_post to the real server app with injectable faults."""

    def __init__(self, http, headers, faults=(), max_calls=12, drop_ack=0):
        self.http, self.headers = http, headers
        self.faults, self.max_calls, self.drop_ack = list(faults), max_calls, drop_ack
        self.calls = []

    def __call__(self, config, endpoint, data):
        self.calls.append((endpoint, json.loads(json.dumps(data))))
        if len(self.calls) > self.max_calls:
            raise StopLoop()
        if endpoint == "/tasks/result" and self.faults:
            fault = self.faults.pop(0)
            if fault == "network":
                return None, "timed out"
            return None, f"HTTP Error {fault}: injected"
        r = self.http.post(endpoint, headers=self.headers, json=data)
        if endpoint == "/tasks/result" and self.drop_ack:
            self.drop_ack -= 1  # server processed it, but the ACK is lost
            return None, "connection reset"
        if r.status_code >= 400:
            return None, f"HTTP Error {r.status_code}: {r.get_data(as_text=True)}"
        return r.get_json(), None

    def posted(self, endpoint):
        return [d for e, d in self.calls if e == endpoint]


def go(daemon, monkeypatch, bridge, executions, effect=None, status="SUCCESS", tmp_path=None):
    def execute(packet, config):
        executions.append(packet["task_id"])
        if effect is not None:
            effect.write_text("done\n")
        return {"status": status, "stdout": "", "stderr": "", "execution_mode": "NATIVE"}

    monkeypatch.setattr(daemon, "http_post", bridge)
    monkeypatch.setattr(daemon, "run_native", execute)
    monkeypatch.setattr(daemon, "run_agy", execute)
    with pytest.raises(StopLoop):
        daemon.loop()


def test_success_is_bound_and_accepted(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    monkeypatch.chdir(tmp_path)
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    go(daemon, monkeypatch, Bridge(http, headers, max_calls=4), executions, effect=tmp_path / "effect.txt")
    task = srv.load_state()["tasks"]["task-1"]
    assert task["status"] == "RESULT_RECEIVED"
    assert task["result"]["artifacts"] == [
        {"path": "effect.txt", "sha256": hashlib.sha256(b"done\n").hexdigest()}]
    assert executions == ["task-1"]


def test_crash_after_post_before_ack_resends_same_result_once_executed(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    monkeypatch.chdir(tmp_path)
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    bridge = Bridge(http, headers, drop_ack=1, max_calls=6)
    go(daemon, monkeypatch, bridge, executions, effect=tmp_path / "effect.txt")
    posted = bridge.posted("/tasks/result")
    assert len(posted) >= 2 and all(p == posted[0] for p in posted)
    assert executions == ["task-1"]
    assert srv.load_state()["tasks"]["task-1"]["status"] == "RESULT_RECEIVED"
    assert not state_file(daemon).exists()


def test_restart_with_result_ready_redelivers_to_server_without_executing(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    monkeypatch.chdir(tmp_path)
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    go(daemon, monkeypatch, Bridge(http, headers, faults=["network"] * 8, max_calls=12),
       executions, effect=tmp_path / "effect.txt")
    stored = json.loads(state_file(daemon).read_text())
    assert stored["worker_phase"] == "RESULT_READY"
    # Restart twice: the stored result is delivered, never recomputed.
    for _ in range(2):
        daemon2 = load_daemon_again(tmp_path, monkeypatch)
        bridge = Bridge(http, headers, max_calls=4)
        go(daemon2, monkeypatch, bridge, executions)
        for p in bridge.posted("/tasks/result"):
            assert p == stored["result_payload"]
    assert executions == ["task-1"]
    assert srv.load_state()["tasks"]["task-1"]["status"] == "RESULT_RECEIVED"


def load_daemon_again(tmp_path, monkeypatch):
    import shutil
    for d in ("state", "logs"):
        shutil.copytree(tmp_path / d, tmp_path / f"{d}.bak", dirs_exist_ok=True)
        shutil.rmtree(tmp_path / d)
    daemon = load_daemon(tmp_path, monkeypatch)
    for d in ("state", "logs"):
        shutil.copytree(tmp_path / f"{d}.bak", tmp_path / d, dirs_exist_ok=True)
        shutil.rmtree(tmp_path / f"{d}.bak")
    return daemon


def test_rejected_result_releases_worker_instead_of_permanent_busy(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    monkeypatch.chdir(tmp_path)
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    bridge = Bridge(http, headers, faults=[400], max_calls=10)
    go(daemon, monkeypatch, bridge, executions, effect=tmp_path / "effect.txt")
    assert executions == ["task-1"]
    assert len(bridge.posted("/tasks/result")) == 1
    state = srv.load_state()
    assert state["tasks"]["task-1"]["status"] == "HUMAN_REQUIRED"
    assert state["workers"]["MAC-01"]["current_task"] is None
    assert not state_file(daemon).exists()


def test_crash_after_rejection_still_releases_on_restart(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    claimed = http.post("/tasks/claim", headers=headers, json={"worker_id": "MAC-01"}).get_json()["task"]
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    state_file(daemon).write_text(json.dumps(dict(claimed, worker_phase="RELEASE_PENDING")))
    go(daemon, monkeypatch, Bridge(http, headers, max_calls=5), executions)
    assert executions == []
    assert srv.load_state()["tasks"]["task-1"]["status"] == "HUMAN_REQUIRED"
    assert srv.load_state()["workers"]["MAC-01"]["current_task"] is None


@pytest.mark.parametrize("bad", ["../outside.txt", "/etc/passwd", "a/../../x.txt"])
def test_unsafe_artifact_is_never_read_and_never_success(tmp_path, monkeypatch, bad):
    work = tmp_path / "work"
    work.mkdir()
    (tmp_path / "outside.txt").write_text("secret")
    srv, http, headers = central(tmp_path, monkeypatch, artifacts=(bad,))
    monkeypatch.chdir(work)
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    read = []
    real = daemon.Path.read_bytes
    monkeypatch.setattr(daemon.Path, "read_bytes", lambda self: read.append(str(self)) or real(self))
    bridge = Bridge(http, headers, max_calls=4)
    go(daemon, monkeypatch, bridge, executions)
    [posted] = bridge.posted("/tasks/result")[:1]
    assert posted["status"] == "FAILED" and posted["artifacts"] == []
    assert read == []


def test_success_without_any_artifact_evidence_is_reported_failed(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    monkeypatch.chdir(tmp_path)
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    bridge = Bridge(http, headers, max_calls=4)
    go(daemon, monkeypatch, bridge, executions)  # no effect written
    [posted] = bridge.posted("/tasks/result")
    assert posted["status"] == "FAILED" and posted["artifacts"] == []
    assert srv.load_state()["tasks"]["task-1"]["status"] == "QUEUED"  # retryable, worker free
    assert srv.load_state()["workers"]["MAC-01"]["current_task"] is None


def test_missing_api_key_fails_closed_before_network(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    monkeypatch.setattr(daemon, "load_config", lambda: {
        "COURIER_SERVER": "http://courier.invalid", "WORKER_ID": "MAC-01", "COURIER_API_KEY": "  "})
    calls = []
    monkeypatch.setattr(daemon, "http_post", lambda *a: calls.append(a) or ({}, None))
    with pytest.raises(SystemExit) as exc:
        daemon.loop()
    assert exc.value.code == 2
    assert calls == []
