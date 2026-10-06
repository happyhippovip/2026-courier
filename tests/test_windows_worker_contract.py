"""Windows worker recovery against the real server contract (no live Windows)."""
import hashlib
import importlib
import importlib.util
import json
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path

import pytest

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "windows_worker" / "daemon.py"


class StopLoop(BaseException):
    """Ends daemon.loop(); BaseException passes through its `except Exception`."""


def load_daemon(tmp_path, monkeypatch):
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path))
    spec = importlib.util.spec_from_file_location("windows_worker_daemon_under_test", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    
    config_path = daemon.APP_DATA_DIR / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps({
        "COURIER_SERVER": "http://courier.invalid", 
        "WORKER_ID": "WIN-01",
        "COURIER_API_KEY": "dummy-test-key-not-real",
        "ARTIFACT_UPLOAD": "false"  # Default off to avoid complex artifact mocks unless testing them
    }))
    
    monkeypatch.setattr(daemon.time, "sleep", lambda seconds: None)
    return daemon


def central(tmp_path, monkeypatch, artifacts=("effect.txt",)):
    monkeypatch.setenv("COURIER_API_KEY", "test-secret")
    monkeypatch.setenv("COURIER_VERIFIER_API_KEY", "verifier-secret")
    srv = importlib.import_module("server.app")
    monkeypatch.setattr(srv, "STATE_FILE", str(tmp_path / "central.json"))
    monkeypatch.setattr(srv, "API_KEY", "test-secret")
    http = srv.app.test_client()
    headers = {"Authorization": "Bearer test-secret", "Content-Type": "application/json"}
    http.post("/workers/register", headers=headers,
              json={"worker_id": "WIN-01", "platform": "windows", "capabilities": ["windows"]})
    http.post("/goals", headers=headers, json={"goal_text": "g", "workflow_plan": [
        {"task_id": "task-1", "target_agent": "windows", "artifacts": list(artifacts)}]})
    return srv, http, headers


class UrllibResponse:
    def __init__(self, data, status):
        self.data = data
        self.status = status
    def read(self): return self.data
    def decode(self, *a, **k): return self.data.decode(*a, **k)
    def __enter__(self): return self
    def __exit__(self, *a): pass


class Bridge:
    """Routes urllib.request.urlopen to the real server app with injectable faults."""

    def __init__(self, http, headers, faults=(), max_calls=12, drop_ack=0):
        self.http, self.headers = http, headers
        self.faults, self.max_calls, self.drop_ack = list(faults), max_calls, drop_ack
        self.calls = []

    def __call__(self, req, data=None, timeout=None):
        endpoint = req.full_url.replace("http://courier.invalid", "")
        # req.data is bytes if available, but data param might also be passed
        payload_bytes = data if data is not None else req.data
        payload = json.loads(payload_bytes) if payload_bytes else None
        
        self.calls.append((endpoint, payload))
        if len(self.calls) > self.max_calls:
            raise StopLoop()
            
        if endpoint == "/tasks/result" and self.faults:
            fault = self.faults.pop(0)
            if fault == "network":
                raise urllib.error.URLError("timed out")
            raise urllib.error.HTTPError(req.full_url, fault, "injected", {}, BytesIO(b""))

        headers = dict(self.headers)
        if payload is not None:
            r = self.http.post(endpoint, headers=headers, json=payload)
        else:
            r = self.http.post(endpoint, headers=headers)
            
        if endpoint == "/tasks/result" and self.drop_ack:
            self.drop_ack -= 1
            raise urllib.error.URLError("connection reset")
            
        if r.status_code >= 400:
            raise urllib.error.HTTPError(req.full_url, r.status_code, "error", {}, BytesIO(r.get_data()))
            
        return UrllibResponse(r.get_data(), r.status_code)

    def posted(self, endpoint):
        return [d for e, d in self.calls if e == endpoint]


def state_file(daemon):
    return daemon.STATE_DIR / "current_task.json"


def load_daemon_again(tmp_path, monkeypatch):
    import shutil
    pd = tmp_path / "CourierWorker"
    for d in ("state", "logs"):
        shutil.copytree(pd / d, pd / f"{d}.bak", dirs_exist_ok=True)
        shutil.rmtree(pd / d)
    daemon = load_daemon(tmp_path, monkeypatch)
    for d in ("state", "logs"):
        shutil.copytree(pd / f"{d}.bak", pd / d, dirs_exist_ok=True)
        shutil.rmtree(pd / f"{d}.bak")
    return daemon


def go(daemon, monkeypatch, bridge, executions, effect=None, status="SUCCESS", tmp_path=None):
    def execute(task, config):
        executions.append(task["task_id"])
        if effect is not None:
            effect.write_bytes(b"done\n")
        return {"status": status, "stdout": "", "stderr": "", "run_id": "win-native"}

    monkeypatch.setattr(daemon.urllib.request, "urlopen", bridge)
    monkeypatch.setattr(daemon, "run_task", execute)
    # Don't fail the loop on lock acquisition
    monkeypatch.setattr(daemon, "acquire_lock", lambda w: tmp_path / "mock.lock")
    with pytest.raises(StopLoop):
        daemon.loop()


def test_success_is_bound_and_accepted(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    monkeypatch.chdir(daemon.APP_DATA_DIR)  # worker runs from some cwd, artifacts relative to it
    effect = daemon.APP_DATA_DIR / "effect.txt"
    go(daemon, monkeypatch, Bridge(http, headers, max_calls=4), executions, effect=effect, tmp_path=tmp_path)
    
    task = srv.load_state()["tasks"]["task-1"]
    assert task["status"] == "RESULT_RECEIVED"
    assert task["result"]["artifacts"] == [
        {"path": "effect.txt", "sha256": hashlib.sha256(b"done\n").hexdigest()}]
    assert executions == ["task-1"]


def test_crash_after_post_before_ack_resends_same_result_once_executed(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    monkeypatch.chdir(daemon.APP_DATA_DIR)
    bridge = Bridge(http, headers, drop_ack=1, max_calls=6)
    go(daemon, monkeypatch, bridge, executions, effect=daemon.APP_DATA_DIR / "effect.txt", tmp_path=tmp_path)
    
    posted = bridge.posted("/tasks/result")
    assert len(posted) >= 2 and all(p == posted[0] for p in posted)
    assert executions == ["task-1"]
    assert srv.load_state()["tasks"]["task-1"]["status"] == "RESULT_RECEIVED"
    assert not state_file(daemon).exists()


def test_restart_with_result_ready_redelivers_to_server_without_executing(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    monkeypatch.chdir(daemon.APP_DATA_DIR)
    go(daemon, monkeypatch, Bridge(http, headers, faults=["network"] * 10, max_calls=8),
       executions, effect=daemon.APP_DATA_DIR / "effect.txt", tmp_path=tmp_path)
       
    stored = json.loads(state_file(daemon).read_text())
    assert stored["worker_phase"] == "RESULT_READY"
    
    for _ in range(2):
        daemon2 = load_daemon_again(tmp_path, monkeypatch)
        bridge = Bridge(http, headers, max_calls=4)
        go(daemon2, monkeypatch, bridge, executions, tmp_path=tmp_path)
        for p in bridge.posted("/tasks/result"):
            assert p == stored["result_payload"]
            
    assert executions == ["task-1"]
    assert srv.load_state()["tasks"]["task-1"]["status"] == "RESULT_RECEIVED"


def test_rejected_result_releases_worker_instead_of_permanent_busy(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    monkeypatch.chdir(daemon.APP_DATA_DIR)
    bridge = Bridge(http, headers, faults=[400], max_calls=10)
    go(daemon, monkeypatch, bridge, executions, effect=daemon.APP_DATA_DIR / "effect.txt", tmp_path=tmp_path)
    
    assert executions == ["task-1"]
    assert len(bridge.posted("/tasks/result")) == 1
    state = srv.load_state()
    assert state["tasks"]["task-1"]["status"] == "HUMAN_REQUIRED"
    assert state["workers"]["WIN-01"]["current_task"] is None
    assert not state_file(daemon).exists()


def test_crash_after_rejection_still_releases_on_restart(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    claimed = http.post("/tasks/claim", headers=headers, json={"worker_id": "WIN-01"}).get_json()["task"]
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    state_file(daemon).write_text(json.dumps(dict(claimed, worker_phase="RELEASE_PENDING")))
    
    go(daemon, monkeypatch, Bridge(http, headers, max_calls=5), executions, tmp_path=tmp_path)
    
    assert executions == []
    assert srv.load_state()["tasks"]["task-1"]["status"] == "HUMAN_REQUIRED"
    assert srv.load_state()["workers"]["WIN-01"]["current_task"] is None


@pytest.mark.parametrize("bad", ["../outside.txt", "/etc/passwd", "a/../../x.txt", "C:/Windows/System32"])
def test_unsafe_artifact_is_never_read_and_never_success(tmp_path, monkeypatch, bad):
    srv, http, headers = central(tmp_path, monkeypatch, artifacts=(bad,))
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    work = daemon.APP_DATA_DIR / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    
    (tmp_path / "outside.txt").write_text("secret")
    
    read = []
    real = daemon.Path.read_bytes
    monkeypatch.setattr(daemon.Path, "read_bytes", lambda self: read.append(str(self)) or real(self))
    
    bridge = Bridge(http, headers, max_calls=4)
    go(daemon, monkeypatch, bridge, executions, tmp_path=tmp_path)
    
    [posted] = bridge.posted("/tasks/result")[:1]
    assert posted["status"] == "FAILED" and posted["artifacts"] == []
    assert read == []


def test_success_without_any_artifact_evidence_is_reported_failed(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    monkeypatch.chdir(daemon.APP_DATA_DIR)
    bridge = Bridge(http, headers, max_calls=4)
    
    go(daemon, monkeypatch, bridge, executions, tmp_path=tmp_path)  # no effect written
    
    [posted] = bridge.posted("/tasks/result")
    assert posted["status"] == "FAILED" and posted["artifacts"] == []
    assert srv.load_state()["tasks"]["task-1"]["status"] == "QUEUED"
    assert srv.load_state()["workers"]["WIN-01"]["current_task"] is None


def test_missing_api_key_fails_closed_before_network(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    config_path = daemon.APP_DATA_DIR / "config.json"
    cfg = json.loads(config_path.read_text())
    cfg["COURIER_API_KEY"] = ""
    config_path.write_text(json.dumps(cfg))
    # Remove key from module state
    daemon.API_KEY = ""
    monkeypatch.setenv("COURIER_API_KEY", "")
    calls = []
    monkeypatch.setattr(daemon.urllib.request, "urlopen", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(daemon, "acquire_lock", lambda w: tmp_path / "mock.lock")
    
    with pytest.raises(daemon.MissingCredentialError) as exc:
        daemon.loop()
        
    assert "COURIER_API_KEY is not set" in str(exc.value)
    assert calls == []
