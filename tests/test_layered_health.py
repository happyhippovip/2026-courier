"""Tests for Layered Health Model (FRZ-06)."""

from __future__ import annotations

import pytest

from scripts.layered_health import (
    FailureClassification,
    LayerState,
    assess_agent_session_layer,
    assess_persistent_state_layer,
    assess_surface_layer,
    assess_terminal_host_layer,
    assess_work_execution_layer,
    evaluate_system_layered_health,
)


def test_assess_work_execution_layer_active_claim_dead_worker():
    """Verify in-flight work claims with dead worker triggers FAILED state."""
    owned_procs = {"worker": {"alive": False, "pid": 123}}
    claims = [{"dispatch_id": "disp-1"}]
    res = assess_work_execution_layer(owned_procs, claims)
    assert res["state"] == LayerState.FAILED.value
    assert len(res["reasons"]) > 0


def test_assess_work_execution_layer_healthy():
    """Verify running worker with or without claims is healthy."""
    owned_procs = {"worker": {"alive": True, "pid": 123}}
    claims = [{"dispatch_id": "disp-1"}]
    res = assess_work_execution_layer(owned_procs, claims)
    assert res["state"] == LayerState.HEALTHY.value
    assert res["worker_alive"] is True


def test_assess_surface_layer_independent_of_work():
    """Verify dead surface hub is degraded without implying work failed."""
    owned_procs = {"hub": {"alive": False, "pid": 456}}
    res = assess_surface_layer(owned_procs)
    assert res["state"] == LayerState.DEGRADED.value
    assert res["hub_alive"] is False


def test_assess_terminal_host_layer():
    """Verify terminal host assessment."""
    res = assess_terminal_host_layer()
    assert res["layer"] == "TERMINAL_HOST"
    assert res["state"] == LayerState.HEALTHY.value


def test_assess_persistent_state_layer_unpushed_cap():
    """Verify excessive unpushed commits trigger FAILED state (incident scenario: 71 commits)."""
    journal = {"exists": True}
    git_st = {"dirty_count": 0, "unpushed_count": 71}
    res = assess_persistent_state_layer(journal, git_st)
    assert res["state"] == LayerState.FAILED.value
    assert FailureClassification.PERSISTENCE_UNPUSHED_CAP_EXCEEDED.value in res["classifications"]


def test_assess_persistent_state_layer_healthy():
    """Verify low unpushed commits and dirty files is healthy."""
    journal = {"exists": True}
    git_st = {"dirty_count": 2, "unpushed_count": 1}
    res = assess_persistent_state_layer(journal, git_st)
    assert res["state"] == LayerState.HEALTHY.value
    assert len(res["classifications"]) == 0


def test_evaluate_system_layered_health_structure(tmp_path):
    """Verify full evaluation structure contains all 5 canonical layers."""
    report = evaluate_system_layered_health(app_data_dir=tmp_path)
    assert report["schema_version"] == "1.0"
    assert "work_execution" in report["layers"]
    assert "surface_ui" in report["layers"]
    assert "terminal_host" in report["layers"]
    assert "agent_session" in report["layers"]
    assert "persistent_state" in report["layers"]
    assert "resources" in report
