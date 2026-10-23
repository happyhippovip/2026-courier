"""A ready Windows result must be posted while CPU pressure blocks new claims.

The production probe stays on the path. Only the load sample is synthetic.
daemon.py is owned by other open pull requests, so the missing delivery is
recorded here and not patched in this branch.
"""
import json

import pytest

from tests.test_windows_worker_contract import Bridge, StopLoop, central, load_daemon


def _ready_result(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    daemon = load_daemon(tmp_path, monkeypatch)
    monkeypatch.chdir(daemon.APP_DATA_DIR)
    claimed = http.post("/tasks/claim", headers=headers, json={"worker_id": "WIN-01"})
    assert claimed.status_code == 200
    task = claimed.get_json()["task"]
    payload = daemon.build_result_payload(
        task,
        {"status": "FAILED", "stdout": "", "stderr": "no artifact", "run_id": "win-native"},
        {"WORKER_ID": "WIN-01"},
    )
    task["worker_phase"] = "RESULT_READY"
    task["result_payload"] = payload
    daemon.persist_task(daemon.STATE_DIR / "current_task.json", task)
    return srv, http, headers, daemon


def test_synthetic_pressure_uses_the_production_guard(tmp_path, monkeypatch):
    _srv, _http, _headers, daemon = _ready_result(tmp_path, monkeypatch)
    monkeypatch.setattr(daemon, "read_cpu_load_percent", lambda: 95.0)
    assert daemon.is_resource_pressure_high() is True
    monkeypatch.setattr(daemon, "read_cpu_load_percent", lambda: 10.0)
    assert daemon.is_resource_pressure_high() is False


def test_pressure_stop_leaves_the_ready_result_unposted(tmp_path, monkeypatch):
    """CW10-04..08. StopLoop is the test budget. The loop itself never posts."""
    srv, _http, headers, daemon = _ready_result(tmp_path, monkeypatch)
    monkeypatch.setattr(daemon, "read_cpu_load_percent", lambda: 95.0)
    bridge = Bridge(_http, headers, max_calls=4)
    monkeypatch.setattr(daemon.urllib.request, "urlopen", bridge)
    with pytest.raises(StopLoop):
        daemon.loop()
    endpoints = [endpoint for endpoint, _payload in bridge.calls]
    assert endpoints == ["/workers/heartbeat"] * 5
    stored = json.loads((daemon.STATE_DIR / "current_task.json").read_text(encoding="utf-8"))
    assert stored["worker_phase"] == "RESULT_READY"
    assert srv.load_state()["tasks"]["task-1"]["status"] == "DISPATCHED"


@pytest.mark.xfail(
    strict=True,
    reason="daemon.loop pauses before posting RESULT_READY while CPU load is above 85 percent. "
    "scripts/windows_worker/daemon.py is leased by open PRs #190 and #788.",
)
def test_ready_result_is_posted_while_pressure_blocks_a_new_claim(tmp_path, monkeypatch):
    srv, http, headers, daemon = _ready_result(tmp_path, monkeypatch)
    monkeypatch.setattr(daemon, "read_cpu_load_percent", lambda: 95.0)
    bridge = Bridge(http, headers, max_calls=4)
    monkeypatch.setattr(daemon.urllib.request, "urlopen", bridge)
    with pytest.raises(StopLoop):
        daemon.loop()
    endpoints = [endpoint for endpoint, _payload in bridge.calls]
    assert "/tasks/result" in endpoints
    assert "/tasks/claim" not in endpoints
    assert not (daemon.STATE_DIR / "current_task.json").exists()
    assert srv.load_state()["tasks"]["task-1"]["status"] == "QUEUED"
