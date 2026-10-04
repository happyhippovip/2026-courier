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
