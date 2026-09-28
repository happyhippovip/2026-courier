"""Deeper Windows worker contract checks (mocked PowerShell, real server app)."""
import json

import pytest

from test_windows_worker_binding import Harness, central, load_daemon, run, state_file


def test_rejected_result_releases_worker_instead_of_permanent_busy(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    harness, executions = Harness(http, headers, faults=[400], max_calls=10), []
    daemon = load_daemon(tmp_path, monkeypatch, harness, executions)

    run(daemon)

    assert len(executions) == 1
    releases = [b for b in harness.posted("/workers/register") if "current_task" in b]
    assert releases and releases[0]["current_task"] is None
    state = srv.load_state()
    assert state["tasks"]["w1"]["status"] == "HUMAN_REQUIRED"
    assert state["workers"]["WINDOWS-01"]["current_task"] is None
    assert state["workers"]["WINDOWS-01"]["available"] is True
    # Evidence of the rejected payload is kept locally.
    assert (daemon.STATE_DIR / "rejected_result_w1.json").is_file()


def test_result_id_is_stable_across_every_resend(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    harness, executions = Harness(http, headers, faults=["network", 503, "network"], max_calls=12), []
    daemon = load_daemon(tmp_path, monkeypatch, harness, executions)

    run(daemon)

    posted = harness.posted("/tasks/result")
    assert len(posted) >= 4 and len({p["result_id"] for p in posted}) == 1
    assert len(executions) == 1
    assert srv.load_state()["tasks"]["w1"]["status"] == "RESULT_RECEIVED"


def test_relative_artifact_resolves_in_worker_workspace(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    harness, executions = Harness(http, headers, max_calls=4), []
    daemon = load_daemon(tmp_path, monkeypatch, harness, executions)

    run(daemon)

    [posted] = harness.posted("/tasks/result")
    assert posted["status"] == "SUCCESS"
    assert posted["artifacts"][0]["path"] == "win.txt"
    import hashlib
    assert posted["artifacts"][0]["sha256"] == hashlib.sha256((tmp_path / "win.txt").read_bytes()).hexdigest()


@pytest.mark.parametrize("bad", ["../outside.txt", "..\\outside.txt", "/etc/passwd", "C:\\Windows\\win.ini",
                                 "C:outside.txt", "\\\\server\\share\\x.txt", "sub/../../x.txt"])
def test_unsafe_artifact_path_is_never_read_and_never_success(tmp_path, monkeypatch, bad):
    work = tmp_path / "work"
    work.mkdir()
    (tmp_path / "outside.txt").write_text("secret")
    srv, http, headers = central(tmp_path, monkeypatch, artifacts=(bad,))
    harness, executions = Harness(http, headers, max_calls=6), []
    daemon = load_daemon(tmp_path, monkeypatch, harness, executions)
    monkeypatch.chdir(work)
    read = []
    real_read = daemon.Path.read_bytes
    monkeypatch.setattr(daemon.Path, "read_bytes", lambda self: read.append(str(self)) or real_read(self))

    run(daemon)

    posted = harness.posted("/tasks/result")
    assert posted and posted[0]["status"] == "FAILED" and posted[0]["artifacts"] == []
    assert read == []


def test_expected_canary_artifact_is_bound(tmp_path, monkeypatch):
    import importlib
    monkeypatch.setenv("COURIER_API_KEY", "test-secret")
    srv = importlib.import_module("server.app")
    monkeypatch.setattr(srv, "STATE_FILE", str(tmp_path / "central.json"))
    monkeypatch.setattr(srv, "API_KEY", "test-secret")
    http, headers = srv.app.test_client(), {"Authorization": "Bearer test-secret"}
    http.post("/workers/register", headers=headers,
              json={"worker_id": "WINDOWS-01", "platform": "windows", "capabilities": ["windows"]})
    http.post("/goals", headers=headers, json={"goal_text": "g", "workflow_plan": [
        {"task_id": "w1", "target_agent": "windows", "instruction": "canary"}]})
    harness, executions = Harness(http, headers, max_calls=4), []
    daemon = load_daemon(tmp_path, monkeypatch, harness, executions, effect=False)
    # No artifacts given: the contract defaults to the canary file.
    monkeypatch.setattr(daemon.subprocess, "Popen", _writer(tmp_path / "courier_canary_w1.txt", executions))

    run(daemon)

    [posted] = harness.posted("/tasks/result")
    assert posted["status"] == "SUCCESS"
    assert [a["path"] for a in posted["artifacts"]] == ["courier_canary_w1.txt"]


def _writer(path, executions):
    class P:
        pid, returncode = 1, 0

        def __init__(self, *a, **k):
            executions.append(a[0])
            path.write_text("SUCCESS\n")

        def communicate(self, timeout=None):
            return "", ""
    return P


def test_success_cannot_claim_nonexistent_artifact(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch, artifacts=("win.txt", "missing.txt"))
    harness, executions = Harness(http, headers, max_calls=4), []
    daemon = load_daemon(tmp_path, monkeypatch, harness, executions)

    run(daemon)

    [posted] = harness.posted("/tasks/result")
    assert posted["status"] == "FAILED" and posted["artifacts"] == []
    assert "missing.txt" in posted["stderr"]


def test_registration_advertises_only_executable_capability(tmp_path, monkeypatch):
    """config.json lists antigravity/powershell/cmd, but run_task only executes
    PowerShell; advertising 'antigravity' would route agy tasks here."""
    srv, http, headers = central(tmp_path, monkeypatch)
    harness, executions = Harness(http, headers, max_calls=3), []
    daemon = load_daemon(tmp_path, monkeypatch, harness, executions)
    monkeypatch.setattr(daemon, "load_config", lambda: {
        "WORKER_ID": "WINDOWS-01", "WORKER_CAPABILITIES": ["windows", "antigravity", "powershell", "cmd"]})
    daemon.register_worker("WINDOWS-01")
    [reg] = harness.posted("/workers/register")
    assert reg["capabilities"] == ["windows"]


def test_crash_after_rejection_still_releases_on_restart(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    claimed = http.post("/tasks/claim", headers=headers, json={"worker_id": "WINDOWS-01"}).get_json()["task"]
    harness, executions = Harness(http, headers, max_calls=5), []
    daemon = load_daemon(tmp_path, monkeypatch, harness, executions)
    daemon.persist_task(state_file(daemon), dict(claimed, worker_phase="RELEASE_PENDING"))

    run(daemon)

    assert executions == [] and harness.posted("/tasks/result") == []
    assert srv.load_state()["tasks"]["w1"]["status"] == "HUMAN_REQUIRED"
    assert srv.load_state()["workers"]["WINDOWS-01"]["current_task"] is None
    assert not state_file(daemon).exists()

def test_run_task_kills_process_on_timeout(monkeypatch):
    import subprocess
    import scripts.windows_worker.daemon as daemon
    class MockProcess:
        def __init__(self):
            self.pid = 1234
            self.returncode = None
            self.killed = False
        def communicate(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd="powershell", timeout=timeout)
        def kill(self):
            self.killed = True
    
    mock_p = MockProcess()
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: mock_p)
    
    res = daemon.run_task({"task_id": "t1", "instruction": "sleep"}, {"WORKER_ID": "W1"})
    assert res["status"] == "FAILED"
    assert "timed out" in res["stderr"]
    assert mock_p.killed is True

def test_resource_pressure_does_not_block_result_ready_phase(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    harness, executions = Harness(http, headers, max_calls=2), []
    import scripts.windows_worker.daemon as daemon
    
    claimed = http.post("/tasks/claim", headers=headers, json={"worker_id": "WINDOWS-01"}).get_json()["task"]
    
    # Mock high pressure
    monkeypatch.setattr(daemon, "is_resource_pressure_high", lambda: True)
    
    # Start the daemon with a RESULT_READY task
    d = load_daemon(tmp_path, monkeypatch, harness, executions)
    d.persist_task(state_file(d), dict(claimed, worker_phase="RESULT_READY", result_payload={
        "goal_id": claimed["goal_id"], "task_id": claimed["task_id"], "worker_id": "WINDOWS-01",
        "run_id": "r1", "result_id": "r2", "status": "FAILED", "artifacts": [],
        "attempt_id": claimed["attempt_id"], "dispatch_id": claimed["dispatch_id"]
    }))
    
    run(d)
    
    # Despite high pressure, it should have delivered the result!
    state = srv.load_state()
    assert state["tasks"][claimed["task_id"]]["status"] == "QUEUED"

def test_is_safe_artifact_path():
    from scripts.windows_worker.daemon import is_safe_artifact_path
    
    # Safe paths
    assert is_safe_artifact_path("file.txt") is True
    assert is_safe_artifact_path("folder/file.txt") is True
    assert is_safe_artifact_path("folder\\file.txt") is True
    
    # Unsafe paths
    assert is_safe_artifact_path("../file.txt") is False
    assert is_safe_artifact_path("folder/../file.txt") is False
    assert is_safe_artifact_path("/file.txt") is False
    assert is_safe_artifact_path("\\file.txt") is False
    assert is_safe_artifact_path("C:\\file.txt") is False
    assert is_safe_artifact_path("C:file.txt") is False
    assert is_safe_artifact_path("\\\\?\\C:\\file.txt") is False
    assert is_safe_artifact_path(None) is False
    assert is_safe_artifact_path("") is False

def test_upload_artifact_success(tmp_path, monkeypatch):
    import scripts.windows_worker.daemon as daemon
    import hashlib
    import json
    from urllib.error import HTTPError
    from pathlib import Path
    
    art_path = tmp_path / "test.txt"
    art_path.write_bytes(b"hello")
    digest = hashlib.sha256(b"hello").hexdigest()
    
    # Needs to be relative for is_safe_artifact_path, but wait: is_safe_artifact_path REJECTS absolute paths.
    # So we must mock it or chdir.
    monkeypatch.chdir(tmp_path)
    
    # Create the file in the CWD
    Path("test.txt").write_bytes(b"hello")
    
    task = {"goal_id": "g", "task_id": "t", "attempt_id": "a", "dispatch_id": "d", "worker_id": "w"}
    art = {"path": "test.txt", "sha256": digest}
    
    class MockResponse:
        def read(self):
            return json.dumps({"artifact_id": f"art-{digest}", "size": 5, "sha256": digest}).encode("utf-8")
        def __enter__(self): return self
        def __exit__(self, *args): pass
        
    def mock_urlopen(req, data=None, timeout=None):
        assert req.method == "POST"
        assert req.headers["Content-type"] == "application/octet-stream"
        meta = json.loads(req.headers["X-courier-artifact"])
        assert meta["name"] == "test.txt"
        assert meta["sha256"] == digest
        assert meta["size"] == 5
        assert meta["task_id"] == "t"
        return MockResponse()
        
    monkeypatch.setattr(daemon.urllib.request, "urlopen", mock_urlopen)
    monkeypatch.setattr(daemon, "require_api_key", lambda: None)
    
    outcome, record = daemon.upload_artifact(task, art)
    assert outcome == "OK"
    assert record["artifact_id"] == f"art-{digest}"
    assert record["size"] == 5
