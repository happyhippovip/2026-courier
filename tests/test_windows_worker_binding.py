import importlib
import importlib.util
import io
import json
import urllib.error
from pathlib import Path

import pytest

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "windows_worker" / "daemon.py"


class StopLoop(BaseException):
    """Ends daemon.loop(); passes through its `except Exception`."""


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def central(tmp_path, monkeypatch, artifacts=("win.txt",)):
    monkeypatch.setenv("COURIER_API_KEY", "test-secret")
    monkeypatch.setenv("COURIER_VERIFIER_API_KEY", "verifier-secret")
    srv = importlib.import_module("server.app")
    monkeypatch.setattr(srv, "STATE_FILE", str(tmp_path / "central.json"))
    monkeypatch.setattr(srv, "API_KEY", "test-secret")
    http = srv.app.test_client()
    headers = {"Authorization": "Bearer test-secret"}
    http.post("/workers/register", headers=headers,
              json={"worker_id": "WINDOWS-01", "platform": "windows", "capabilities": ["windows"]})
    http.post("/goals", headers=headers, json={"goal_text": "g", "workflow_plan": [
        {"task_id": "w1", "target_agent": "windows", "instruction": "Set-Content win.txt ok",
         "artifacts": list(artifacts)}]})
    return srv, http, headers


class Harness:
    """Routes the daemon's urllib calls to the real origin/main server app."""

    def __init__(self, http, headers, faults=(), max_calls=12):
        self.http, self.headers = http, headers
        self.faults = list(faults)  # injected per /tasks/result call: None | "network" | int status
        self.max_calls = max_calls
        self.calls = []

    def __call__(self, req, data=None, timeout=None):
        endpoint = req.full_url.split("8080", 1)[-1] if "8080" in req.full_url else req.full_url
        endpoint = "/" + endpoint.split("/", 3)[-1] if endpoint.startswith("http") else endpoint
        body = json.loads(data.decode()) if data else {}
        self.calls.append((endpoint, body))
        if len(self.calls) > self.max_calls:
            raise StopLoop()
        if endpoint == "/tasks/result" and self.faults:
            fault = self.faults.pop(0)
            if fault == "network":
                raise urllib.error.URLError("connection refused")
            if isinstance(fault, int):
                raise urllib.error.HTTPError(req.full_url, fault, "x", {}, io.BytesIO(b"{}"))
        r = self.http.post(endpoint, headers=self.headers, json=body)
        if r.status_code >= 400:
            raise urllib.error.HTTPError(req.full_url, r.status_code, "x", {}, io.BytesIO(r.data))
        return Response(r.data)

    def posted(self, endpoint):
        return [b for e, b in self.calls if e == endpoint]


def load_daemon(tmp_path, monkeypatch, harness, executions, effect=True):
    spec = importlib.util.spec_from_file_location("windows_daemon_under_test", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COURIER_SERVER", raising=False)
    monkeypatch.setattr(daemon, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(daemon, "load_config", lambda: {"WORKER_ID": "WINDOWS-01", "COURIER_SERVER": "http://courier.test:8080",
                                                      "COURIER_API_KEY": "test-worker-key"})
    monkeypatch.setattr(daemon, "acquire_lock", lambda worker_id: tmp_path / "lock")
    monkeypatch.setattr(daemon, "is_resource_pressure_high", lambda: False)
    monkeypatch.setattr(daemon.time, "sleep", lambda s: None)
    monkeypatch.setattr(daemon.urllib.request, "urlopen", harness)

    class FakePowerShell:  # no Windows runtime needed
        pid, returncode = 4242, 0

        def __init__(self, *a, **k):
            executions.append(a[0])
            if effect:
                (tmp_path / "win.txt").write_text("ok\n")

        def communicate(self, timeout=None):
            return "done", ""

    monkeypatch.setattr(daemon.subprocess, "Popen", FakePowerShell)
    return daemon


def run(daemon):
    with pytest.raises(StopLoop):
        daemon.loop()


def state_file(daemon):
    return daemon.STATE_DIR / "current_task.json"


def test_result_carries_binding_and_is_accepted_by_server_contract(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    harness, executions = Harness(http, headers, max_calls=6), []
    daemon = load_daemon(tmp_path, monkeypatch, harness, executions)

    run(daemon)

    [posted] = harness.posted("/tasks/result")
    task = srv.load_state()["tasks"]["w1"]
    for field in ("attempt_id", "dispatch_id", "goal_id", "task_id", "worker_id"):
        assert posted[field] == task[field]
    assert posted["result_id"] and posted["run_id"] == "4242"
    assert posted["artifacts"][0]["path"] == "win.txt"
    assert task["status"] == "RESULT_RECEIVED"
    assert len(executions) == 1
    assert not state_file(daemon).exists()
    # Worker is free again instead of stuck WORKER_BUSY.
    assert srv.load_state()["workers"]["WINDOWS-01"]["current_task"] is None


def test_crash_before_ack_resends_same_result_without_reexecuting(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    claimed = http.post("/tasks/claim", headers=headers, json={"worker_id": "WINDOWS-01"}).get_json()["task"]
    stored = {"goal_id": claimed["goal_id"], "task_id": "w1", "attempt_id": claimed["attempt_id"],
              "dispatch_id": claimed["dispatch_id"], "worker_id": "WINDOWS-01", "run_id": "4242",
              "result_id": "result-stable", "status": "FAILED", "artifacts": []}
    harness, executions = Harness(http, headers, max_calls=2), []
    daemon = load_daemon(tmp_path, monkeypatch, harness, executions)
    daemon.persist_task(state_file(daemon), dict(claimed, worker_phase="RESULT_READY", result_payload=stored))

    run(daemon)

    assert executions == []
    assert harness.posted("/tasks/result")[0] == stored
    assert srv.load_state()["tasks"]["w1"]["result"]["result_id"] == "result-stable"


def test_transient_failures_retry_identical_payload(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    harness, executions = Harness(http, headers, faults=["network", 503], max_calls=8), []
    daemon = load_daemon(tmp_path, monkeypatch, harness, executions)

    run(daemon)

    posts = harness.posted("/tasks/result")
    assert len(posts) == 3 and posts[0] == posts[1] == posts[2]
    assert len(executions) == 1
    assert srv.load_state()["tasks"]["w1"]["status"] == "RESULT_RECEIVED"


def test_undelivered_result_is_kept_and_blocks_new_claims(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    harness, executions = Harness(http, headers, faults=["network"] * 20, max_calls=14), []
    daemon = load_daemon(tmp_path, monkeypatch, harness, executions)

    run(daemon)

    assert len(executions) == 1
    assert len(harness.posted("/tasks/claim")) == 1
    persisted = json.loads(state_file(daemon).read_text())
    assert persisted["worker_phase"] == "RESULT_READY"
    assert all(p == persisted["result_payload"] for p in harness.posted("/tasks/result"))


def test_terminal_4xx_is_not_retried_and_evidence_is_kept(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    harness, executions = Harness(http, headers, faults=[409], max_calls=7), []
    daemon = load_daemon(tmp_path, monkeypatch, harness, executions)

    run(daemon)

    assert len(harness.posted("/tasks/result")) == 1
    assert not state_file(daemon).exists()
    rejected = json.loads((daemon.STATE_DIR / "rejected_result_w1.json").read_text())
    assert rejected["result_payload"] == harness.posted("/tasks/result")[0]


@pytest.mark.parametrize("phase", ["STARTED", None])
def test_started_without_result_is_released_not_reexecuted(tmp_path, monkeypatch, phase):
    srv, http, headers = central(tmp_path, monkeypatch)
    claimed = http.post("/tasks/claim", headers=headers, json={"worker_id": "WINDOWS-01"}).get_json()["task"]
    harness, executions = Harness(http, headers, max_calls=5), []
    daemon = load_daemon(tmp_path, monkeypatch, harness, executions)
    persisted = dict(claimed, worker_phase=phase) if phase else dict(claimed)
    daemon.persist_task(state_file(daemon), persisted)

    run(daemon)

    assert executions == []
    assert harness.posted("/tasks/result") == []
    task = srv.load_state()["tasks"]["w1"]
    assert task["status"] == "HUMAN_REQUIRED"
    assert task["recovery_reason"] == "WORKER_RESTARTED_AND_LOST_STATE"
    assert not state_file(daemon).exists()


def test_missing_artifact_reports_failed_instead_of_contract_violation(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    harness, executions = Harness(http, headers, max_calls=3), []
    daemon = load_daemon(tmp_path, monkeypatch, harness, executions, effect=False)

    run(daemon)

    [posted] = harness.posted("/tasks/result")
    assert posted["status"] == "FAILED" and posted["artifacts"] == []
    # Accepted by the contract: FAILED is requeued for a new attempt, worker freed.
    assert srv.load_state()["tasks"]["w1"]["status"] == "QUEUED"
    assert srv.load_state()["workers"]["WINDOWS-01"]["current_task"] is None
