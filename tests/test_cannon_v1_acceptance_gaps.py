"""Acceptance assertions on the unmodified candidate, not expected-failure tests.

Reuse existing worker/server fixtures. Native work and transport are simulated;
none of these tests is a physical Mac/Windows or power-loss proof.
"""
import copy
import importlib.util
import json

import pytest

import test_mac_worker_contract as mac
import test_mac_worker_recovery as recovery
import test_windows_worker_binding as win
from test_server_integration_contract import auth, durable_result, setup_claimed_task
from server import app as server_app


@pytest.mark.parametrize("field,value", [
    ("result_id", "contradictory-id"), ("worker_id", "OTHER"),
    ("attempt_id", "other-attempt"), ("dispatch_id", "other-dispatch"),
    ("status", "FAILED"), ("artifacts", [{"path": "bounded.txt", "sha256": "f" * 64}]),
])
def test_conflicting_duplicate_is_rejected_not_successfully_ignored(tmp_path, monkeypatch, field, value):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    first = durable_result(task)
    assert http.post("/tasks/result", headers=auth(), json=first).status_code == 200
    before = server_app.load_state()
    conflicting = copy.deepcopy(first)
    conflicting[field] = value
    response = http.post("/tasks/result", headers=auth(), json=conflicting)
    assert server_app.load_state() == before
    assert response.status_code in (400, 409), "contradictory replay must not receive a success ACK"


def test_success_evidence_must_cover_expected_artifact(tmp_path, monkeypatch):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    payload = durable_result(task)
    payload["artifacts"][0]["path"] = "not-the-required-artifact.txt"
    response = http.post("/tasks/result", headers=auth(), json=payload)
    assert response.status_code == 400, "shape-valid evidence is not necessarily the expected effect"
    assert server_app.load_state()["tasks"][task["task_id"]]["status"] == "DISPATCHED"


def test_unpatched_candidate_exposes_artifact_upload(tmp_path, monkeypatch):
    http, _, _ = setup_claimed_task(tmp_path, monkeypatch)
    response = http.post("/artifacts", headers=auth(), data=b"test")
    assert response.status_code == 400, "integrated upload must validate malformed metadata (not 404/500)"


def test_mac_result_is_persisted_before_first_send(tmp_path, monkeypatch):
    _, http, headers = mac.central(tmp_path, monkeypatch)
    monkeypatch.chdir(tmp_path)
    daemon, executions = recovery.load_daemon(tmp_path, monkeypatch), []
    bridge = mac.Bridge(http, headers, max_calls=5)
    persisted = []

    def observe(config, endpoint, payload):
        if endpoint == "/tasks/result":
            disk = json.loads(recovery.state_file(daemon).read_text())
            persisted.append(disk)
            assert disk["worker_phase"] == "RESULT_READY"
            assert disk["result_payload"] == payload
        return bridge(config, endpoint, payload)

    mac.go(daemon, monkeypatch, observe, executions, effect=tmp_path / "effect.txt")
    assert len(persisted) == 1 and executions == ["task-1"]


def test_windows_result_is_persisted_before_first_send(tmp_path, monkeypatch):
    _, http, headers = win.central(tmp_path, monkeypatch)
    harness, executions = win.Harness(http, headers, max_calls=5), []
    daemon = win.load_daemon(tmp_path, monkeypatch, harness, executions)
    persisted = []

    def observe(req, data=None, timeout=None):
        if req.full_url.endswith("/tasks/result"):
            disk = json.loads(win.state_file(daemon).read_text())
            persisted.append(disk)
            assert disk["worker_phase"] == "RESULT_READY"
            assert disk["result_payload"] == json.loads(data)
        return harness(req, data=data, timeout=timeout)

    monkeypatch.setattr(daemon.urllib.request, "urlopen", observe)
    win.run(daemon)
    assert len(persisted) == 1 and len(executions) == 1


@pytest.mark.parametrize("platform", ["mac", "windows"])
def test_persist_fsyncs_file_before_atomic_replace(tmp_path, monkeypatch, platform):
    path = recovery.DAEMON_PATH if platform == "mac" else win.DAEMON_PATH
    spec = importlib.util.spec_from_file_location("persist_under_test", path)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    events = []
    original_sync, original_replace = daemon.os.fsync, daemon.os.replace

    def sync(fd):
        original_sync(fd)
        events.append("fsync")

    def replace(source, destination):
        assert events == ["fsync"]
        original_replace(source, destination)
        events.append("replace")

    monkeypatch.setattr(daemon.os, "fsync", sync)
    monkeypatch.setattr(daemon.os, "replace", replace)
    target = tmp_path / "current_task.json"
    payload = {"worker_phase": "RESULT_READY", "result_payload": {"result_id": "stable"}}
    daemon.persist_task(target, payload)
    assert events == ["fsync", "replace"]
    assert json.loads(target.read_text()) == payload


@pytest.mark.parametrize("code", [400, 401, 403, 404, 409, 422])
@pytest.mark.parametrize("platform", ["mac", "windows"])
def test_permanent_4xx_is_sent_once_and_retained(tmp_path, monkeypatch, code, platform):
    if platform == "mac":
        _, http, headers = mac.central(tmp_path, monkeypatch)
        monkeypatch.chdir(tmp_path)
        daemon, executions = recovery.load_daemon(tmp_path, monkeypatch), []
        transport = mac.Bridge(http, headers, faults=[code], max_calls=7)
        mac.go(daemon, monkeypatch, transport, executions, effect=tmp_path / "effect.txt")
    else:
        _, http, headers = win.central(tmp_path, monkeypatch)
        transport, executions = win.Harness(http, headers, faults=[code], max_calls=7), []
        daemon = win.load_daemon(tmp_path, monkeypatch, transport, executions)
        win.run(daemon)
    assert len(executions) == 1
    assert len(transport.posted("/tasks/result")) == 1
    [rejected] = daemon.STATE_DIR.glob("rejected_result_*.json")
    assert json.loads(rejected.read_text())["result_payload"] == transport.posted("/tasks/result")[0]


@pytest.mark.parametrize("platform", ["mac", "windows"])
def test_completed_packet_redelivery_cannot_execute_same_attempt_twice(tmp_path, monkeypatch, platform):
    # Fault model: identical successful packet delivered twice despite its ACK.
    # Worker-local protection is a distinct invariant from server single-flight.
    if platform == "mac":
        daemon, executions = recovery.load_daemon(tmp_path, monkeypatch), []
        monkeypatch.chdir(tmp_path)
        packet = recovery.task(artifacts=["effect.txt"])
        transport = recovery.FakeServer(claims=[packet, copy.deepcopy(packet)],
                                       results=[({"status": "ACK"}, None)] * 2, max_calls=10)
        mac.go(daemon, monkeypatch, transport, executions, effect=tmp_path / "effect.txt")
    else:
        _, http, headers = win.central(tmp_path, monkeypatch)
        base = win.Harness(http, headers, max_calls=12)
        packets = []

        def duplicate_claim(req, data=None, timeout=None):
            if req.full_url.endswith("/tasks/claim") and packets:
                base.calls.append(("/tasks/claim", {}))
                if len(base.calls) > base.max_calls:
                    raise win.StopLoop()
                return win.Response(json.dumps({"task": packets[0]}).encode())
            response = base(req, data=data, timeout=timeout)
            if req.full_url.endswith("/tasks/claim"):
                body = json.loads(response.getvalue())
                packets.append(body["task"])
            return response

        executions = []
        daemon = win.load_daemon(tmp_path, monkeypatch, duplicate_claim, executions)
        win.run(daemon)
    assert len(executions) == 1, "duplicate delivery replayed an already completed attempt"


@pytest.mark.parametrize("platform", ["mac", "windows"])
def test_failed_result_persistence_must_prevent_send(tmp_path, monkeypatch, platform):
    if platform == "mac":
        _, http, headers = mac.central(tmp_path, monkeypatch)
        monkeypatch.chdir(tmp_path)
        daemon, executions = recovery.load_daemon(tmp_path, monkeypatch), []
        transport = mac.Bridge(http, headers, max_calls=8)
    else:
        _, http, headers = win.central(tmp_path, monkeypatch)
        transport, executions = win.Harness(http, headers, max_calls=8), []
        daemon = win.load_daemon(tmp_path, monkeypatch, transport, executions)
    real_persist = daemon.persist_task
    failures = []

    def fail_ready(path, task):
        if task.get("worker_phase") == "RESULT_READY":
            failures.append(1)
            raise OSError("injected disk-full before durable result")
        return real_persist(path, task)

    monkeypatch.setattr(daemon, "persist_task", fail_ready)
    if platform == "mac":
        mac.go(daemon, monkeypatch, transport, executions, effect=tmp_path / "effect.txt")
    else:
        win.run(daemon)
    assert failures and len(executions) == 1
    assert transport.posted("/tasks/result") == [], "result was sent without successful persistence"


def test_windows_generated_result_survives_restart_without_reexecution(tmp_path, monkeypatch):
    _, http, headers = win.central(tmp_path, monkeypatch)
    failed_transport, executions = win.Harness(http, headers, faults=["network"] * 20, max_calls=14), []
    first = win.load_daemon(tmp_path, monkeypatch, failed_transport, executions)
    win.run(first)
    stored = json.loads(win.state_file(first).read_text())
    assert stored["worker_phase"] == "RESULT_READY" and len(executions) == 1
    healthy = win.Harness(http, headers, max_calls=5)
    restarted = win.load_daemon(tmp_path, monkeypatch, healthy, executions)
    win.run(restarted)
    assert healthy.posted("/tasks/result") == [stored["result_payload"]]
    assert len(executions) == 1
    assert not win.state_file(restarted).exists()


def test_windows_lost_ack_after_server_acceptance_is_idempotent(tmp_path, monkeypatch):
    _, http, headers = win.central(tmp_path, monkeypatch)
    transport, executions = win.Harness(http, headers, max_calls=8), []
    dropped = []

    def lose_ack(req, data=None, timeout=None):
        response = transport(req, data=data, timeout=timeout)
        if req.full_url.endswith("/tasks/result") and not dropped:
            dropped.append(1)
            raise TimeoutError("injected lost ACK after acceptance")
        return response

    daemon = win.load_daemon(tmp_path, monkeypatch, lose_ack, executions)
    win.run(daemon)
    posts = transport.posted("/tasks/result")
    assert len(posts) == 2 and posts[0] == posts[1]
    assert len(executions) == 1


def test_mac_started_restart_is_quarantined_by_server(tmp_path, monkeypatch):
    srv, http, headers = mac.central(tmp_path, monkeypatch)
    claimed = http.post("/tasks/claim", headers=headers, json={"worker_id": "MAC-01"}).get_json()["task"]
    daemon, executions = recovery.load_daemon(tmp_path, monkeypatch), []
    daemon.persist_task(recovery.state_file(daemon), dict(claimed, worker_phase="STARTED"))
    transport = mac.Bridge(http, headers, max_calls=5)
    mac.go(daemon, monkeypatch, transport, executions)
    assert executions == [] and transport.posted("/tasks/result") == []
    assert srv.load_state()["tasks"][claimed["task_id"]]["status"] == "HUMAN_REQUIRED"


def test_failed_result_resend_is_idempotent_after_requeue(tmp_path, monkeypatch):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    failed = dict(durable_result(task), status="FAILED", artifacts=[])
    assert http.post("/tasks/result", headers=auth(), json=failed).status_code == 200
    before = server_app.load_state()
    again = http.post("/tasks/result", headers=auth(), json=failed)
    assert server_app.load_state() == before
    assert again.status_code == 200, "lost ACK of FAILED result must still permit identical resend"


@pytest.mark.parametrize("platform", ["mac", "windows"])
def test_integrated_candidate_upload_and_independent_verification(tmp_path, monkeypatch, platform):
    # Reuse the existing flow assertions but DO NOT apply the preview patch.
    import test_artifact_upload_flow as flow
    from p3_preview import ROOT

    def integrated(directory, patcher):
        patcher.setenv("COURIER_API_KEY", "test-secret")
        patcher.setenv("COURIER_VERIFIER_API_KEY", "verifier-secret")
        patcher.setenv("COURIER_STATE_FILE", str(directory / "central.json"))
        patcher.setenv("COURIER_ARTIFACT_DIR", str(directory / "artifact-store"))
        patcher.setenv("COURIER_ARTIFACT_MAX_BYTES", "4096")
        spec = importlib.util.spec_from_file_location("unpatched_server_under_test", ROOT / "server/app.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    monkeypatch.setattr(flow, "load_patched_server", integrated)
    if platform == "mac":
        flow.test_mac_worker_uploads_and_verifier_reconciles(tmp_path, monkeypatch)
    else:
        flow.test_windows_worker_uploads_and_verifier_reconciles(tmp_path, monkeypatch)
