"""Fail-closed cost gate in WorkerDaemon: missing cost is UNKNOWN, never zero.

Covers courier_core/worker_daemon.py Pre-flight Check (step 2):
cost_spec=None must block without calling the handler; explicit specs
go through evaluate_cost_gate unchanged.
"""
from types import SimpleNamespace

import pytest

from courier_core.worker_daemon import WorkerDaemon


def _daemon(tmp_path, monkeypatch, cost_limit_eur=0.0):
    monkeypatch.setattr(
        "courier_core.worker_daemon.evaluate_resource_health",
        lambda home_path=None, **kw: SimpleNamespace(state="NORMAL", pressure_reasons=[]),
    )
    return WorkerDaemon(
        work_dir=str(tmp_path),
        outbox_dir=str(tmp_path / "outbox"),
        crash_dir=str(tmp_path / "crashes"),
        dlq_file=str(tmp_path / "dlq.json"),
        cost_limit_eur=cost_limit_eur,
    )


def _recording_handler(called):
    def handler():
        called.append(True)
        return {}

    return handler


def test_none_cost_spec_blocked_and_handler_not_called(tmp_path, monkeypatch):
    daemon = _daemon(tmp_path, monkeypatch)
    called = []
    result = daemon.execute_task_cycle("item-1", _recording_handler(called), cost_spec=None)
    assert result.status == "COST_GATE_BLOCKED"
    assert "UNKNOWN_COST" in result.error_message
    assert called == []


def test_missing_cost_estimate_blocked(tmp_path, monkeypatch):
    daemon = _daemon(tmp_path, monkeypatch)
    called = []
    result = daemon.execute_task_cycle(
        "item-1", _recording_handler(called),
        cost_spec={"provider": "local_titan", "model": "v30"},
    )
    assert result.status == "COST_GATE_BLOCKED"
    assert called == []


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), float("-inf"), -1.0, -0.0, True, "x", "0", "abc"])
def test_invalid_cost_values_blocked(tmp_path, monkeypatch, bad):
    daemon = _daemon(tmp_path, monkeypatch)
    called = []
    result = daemon.execute_task_cycle(
        "item-1", _recording_handler(called),
        cost_spec={"provider": "local_titan", "model": "v30", "cost_estimate_eur": bad},
    )
    assert result.status == "COST_GATE_BLOCKED"
    assert called == []


def test_explicit_zero_cost_with_provider_and_model_allowed(tmp_path, monkeypatch):
    daemon = _daemon(tmp_path, monkeypatch)
    called = []
    result = daemon.execute_task_cycle(
        "item-1", _recording_handler(called),
        cost_spec={"provider": "local_titan", "model": "v30", "cost_estimate_eur": 0.0},
    )
    assert called == [True]
    assert result.status == "SUCCESS"


def test_positive_cost_over_limit_blocked_within_limit_allowed(tmp_path, monkeypatch):
    daemon = _daemon(tmp_path, monkeypatch, cost_limit_eur=10.0)
    called = []
    over = daemon.execute_task_cycle(
        "item-1", _recording_handler(called),
        cost_spec={"provider": "p", "model": "m", "cost_estimate_eur": 11.0},
    )
    assert over.status == "COST_GATE_BLOCKED"
    assert called == []
    within = daemon.execute_task_cycle(
        "item-2", _recording_handler(called),
        cost_spec={"provider": "p", "model": "m", "cost_estimate_eur": 5.0},
    )
    assert within.status == "SUCCESS"
    assert called == [True]
