"""CDX-COST-1: the real Codex CLI is a provider run, so CostGate decides before the process starts.

The bridge stamped ``zero_cost_policy: ZERO_COST_ONLY`` on the result but never asked CostGate.
An included quota (ChatGPT Plus) is not a known cost (founder decision 23.10): without an
explicit 0.0 estimate the run is UNKNOWN_COST and must not start.
"""
import json

import pytest

import scripts.run_codex_bridge as codex_bridge


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    monkeypatch.setattr(codex_bridge, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(codex_bridge, "EVENTS_DIR", tmp_path / "events")
    (tmp_path / "events" / "locks").mkdir(parents=True)
    cli = tmp_path / "codex"
    cli.write_text("#!/bin/sh\nexit 0\n")
    monkeypatch.setattr(codex_bridge, "CODEX_CLI_PATH", cli)
    started = []

    def fake_cli(instruction, allowed_scope, task_id):
        started.append(task_id)
        return True, {"verdict": "PASS", "summary": "ok", "agent_source": "CODEX_CLI_REAL"}
    monkeypatch.setattr(codex_bridge, "execute_real_codex_cli", fake_cli)
    hooks = codex_bridge.CodexHookRunner(codex_bridge.CodexVisualStateTracker(repo_dir=tmp_path))
    return tmp_path, hooks, started


def _run(tmp_path, hooks, **job):
    job_file = tmp_path / "job.json"
    job_file.write_text(json.dumps(dict({"task_id": "cdx-1", "instruction": "inspect", "allowed_scope": ["s"]}, **job)))
    return json.loads(codex_bridge.execute_codex_task(job_file, hooks, try_real_cli=True).read_text())


@pytest.mark.parametrize("job", [{}, {"estimated_cost_eur": None}, {"unknown_cost": True, "estimated_cost_eur": 0.0},
                                 {"estimated_cost_eur": float("nan")}, {"estimated_cost_eur": True},
                                 {"estimated_cost_eur": "0"}, {"estimated_cost_eur": 0.5},
                                 {"cost_class": "unknown", "estimated_cost_eur": 0.0}])
def test_the_real_cli_does_not_start_without_a_known_zero_cost(bridge, job):
    tmp_path, hooks, started = bridge
    result = _run(tmp_path, hooks, **job)
    assert started == []
    assert result["status"] == "FAILED" and "COST_GATE_DENIED" in result["payload"]["error"]


def test_the_real_cli_starts_with_an_explicit_zero_estimate(bridge):
    tmp_path, hooks, started = bridge
    result = _run(tmp_path, hooks, estimated_cost_eur=0.0)
    assert started == ["cdx-1"] and result["status"] == "COMPLETED"


def test_a_policy_error_blocks_the_real_cli(bridge, monkeypatch):
    tmp_path, hooks, started = bridge
    from scripts import resource_policy

    def broken(*a, **k):
        raise RuntimeError("policy unreadable")
    monkeypatch.setattr(resource_policy.CostGate, "evaluate_spend_request", staticmethod(broken))
    result = _run(tmp_path, hooks, estimated_cost_eur=0.0)
    assert started == [] and result["status"] == "FAILED"


def test_the_deterministic_path_needs_no_estimate(bridge):
    tmp_path, hooks, started = bridge
    job_file = tmp_path / "job.json"
    job_file.write_text(json.dumps({"task_id": "cdx-2", "instruction": "inspect", "allowed_scope": ["s"]}))
    result = json.loads(codex_bridge.execute_codex_task(job_file, hooks).read_text())
    assert started == [] and result["status"] == "COMPLETED"
