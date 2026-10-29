"""P9 pins for courier_worker.adapter_bridge.write_request (offline).

Scope: the request-envelope contract only - exact keys, workdir/report
mapping, return value, and stale-report invalidation. No source changes,
no network, no credentials, no runner execution (write_request only
writes files under a tmp home; the runner is never spawned).
"""

import json
import os
from types import SimpleNamespace

from courier_worker import adapter_bridge


def _spec(dispatch_id="d1", **overrides):
    fields = {
        "adapter": "synthetic",
        "params": {"steps": 2},
        "attempt": 1,
        "task_id": "t1",
        "dispatch_id": dispatch_id,
        "effect_key": "eff-1",
        "artifact_dir": os.path.join("artifacts", dispatch_id),
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def test_write_request_returns_request_path(tmp_path):
    home = str(tmp_path)
    path = adapter_bridge.write_request(home, _spec("d1"))
    assert path == adapter_bridge.request_path(home, "d1")
    assert os.path.isfile(path)


def test_write_request_envelope_has_exact_keys(tmp_path):
    home = str(tmp_path)
    path = adapter_bridge.write_request(home, _spec("d1"))
    with open(path, encoding="utf-8") as fh:
        envelope = json.load(fh)
    assert set(envelope) == {
        "adapter", "params", "attempt", "task_id",
        "dispatch_id", "effect_key", "workdir", "report",
    }


def test_write_request_maps_workdir_and_report(tmp_path):
    home = str(tmp_path)
    spec = _spec("d9")
    path = adapter_bridge.write_request(home, spec)
    with open(path, encoding="utf-8") as fh:
        envelope = json.load(fh)
    assert envelope["adapter"] == "synthetic"
    assert envelope["params"] == {"steps": 2}
    assert envelope["attempt"] == 1
    assert envelope["task_id"] == "t1"
    assert envelope["dispatch_id"] == "d9"
    assert envelope["effect_key"] == "eff-1"
    assert envelope["workdir"] == spec.artifact_dir
    assert envelope["report"] == adapter_bridge.report_path(home, "d9")


def test_write_request_removes_stale_report(tmp_path):
    home = str(tmp_path)
    stale = adapter_bridge.report_path(home, "d1")
    os.makedirs(os.path.dirname(stale), exist_ok=True)
    with open(stale, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success", "retryable": False}, fh)
    adapter_bridge.write_request(home, _spec("d1"))
    assert not os.path.exists(stale)
    assert adapter_bridge.read_report(home, "d1") is None


def test_write_request_without_stale_report_succeeds(tmp_path):
    home = str(tmp_path)
    assert not os.path.exists(adapter_bridge.report_path(home, "fresh"))
    path = adapter_bridge.write_request(home, _spec("fresh"))
    assert os.path.isfile(path)


def test_write_request_rewrite_clears_newer_report(tmp_path):
    home = str(tmp_path)
    adapter_bridge.write_request(home, _spec("d1", attempt=1))
    interim = adapter_bridge.report_path(home, "d1")
    os.makedirs(os.path.dirname(interim), exist_ok=True)
    with open(interim, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "failure", "retryable": True}, fh)
    path = adapter_bridge.write_request(home, _spec("d1", attempt=2))
    with open(path, encoding="utf-8") as fh:
        envelope = json.load(fh)
    assert envelope["attempt"] == 2
    assert not os.path.exists(interim)


def test_write_request_creates_parent_dirs(tmp_path):
    home = str(tmp_path / "new-home")
    path = adapter_bridge.write_request(home, _spec("d1"))
    assert os.path.isfile(path)


def test_write_request_performs_no_validation(tmp_path):
    home = str(tmp_path)

    def _boom(params):
        raise AssertionError("validator must not run during write_request")

    old = adapter_bridge.ADAPTERS["synthetic"]
    adapter_bridge.ADAPTERS["synthetic"] = _boom
    try:
        path = adapter_bridge.write_request(
            home, _spec("d1", adapter="synthetic", params={"not": "validated"})
        )
    finally:
        adapter_bridge.ADAPTERS["synthetic"] = old
    with open(path, encoding="utf-8") as fh:
        envelope = json.load(fh)
    assert envelope["params"] == {"not": "validated"}
