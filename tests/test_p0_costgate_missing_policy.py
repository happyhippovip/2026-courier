"""Missing, empty, or unreadable policy must not authorize a provider start.

Explicit zero is allowed only when a real policy lists the resource as active.
These tests use fakes. They do not call a provider.
"""
import json
import stat
import sys
import textwrap

import pytest

from scripts.resource_policy import CostGate


def _deny(repo, resource="google_antigravity_plus", **kwargs):
    return CostGate.evaluate_spend_request(resource, repo_dir=repo, **kwargs)


@pytest.mark.parametrize("cost", [0.0, None, float("nan"), float("inf"), float("-inf"), 2.5])
def test_missing_policy_denies_before_any_spend_decision(tmp_path, cost):
    kwargs = {} if cost is None else {"estimated_cost_eur": cost}
    result = _deny(tmp_path, **kwargs)
    assert result["allowed"] is False
    assert result["reason"] == "POLICY_UNAVAILABLE"


def test_empty_and_unreadable_policy_files_deny_explicit_zero(tmp_path):
    folder = tmp_path / "events" / "policies"
    folder.mkdir(parents=True)
    target = folder / "resource_policy.json"
    for body in ("", "{", "{}"):
        target.write_text(body, encoding="utf-8")
        result = _deny(tmp_path, estimated_cost_eur=0.0)
        assert result["allowed"] is False
        assert result["reason"] == "POLICY_UNAVAILABLE"


def test_real_policy_still_allows_only_explicit_zero(tmp_path):
    folder = tmp_path / "events" / "policies"
    folder.mkdir(parents=True)
    (folder / "resource_policy.json").write_text(json.dumps({
        "active_paid_resources": {"google_antigravity_plus": {"status": "ACTIVE_PAID"}},
        "planned_resources": {},
        "unauthorized_resources": {},
    }), encoding="utf-8")
    assert _deny(tmp_path, estimated_cost_eur=0.0)["allowed"] is True
    assert _deny(tmp_path, estimated_cost_eur=1.0)["allowed"] is False
    assert _deny(tmp_path)["allowed"] is False
    assert _deny(tmp_path, estimated_cost_eur=float("nan"))["allowed"] is False


def test_google_builder_missing_policy_does_not_spawn(tmp_path, monkeypatch):
    import scripts.google_builder_worker as gbw

    calls = []

    class _Proc:
        returncode = 0
        stdout = "{}"
        stderr = ""

    def runner(argv, **kwargs):
        calls.append(list(argv))
        return _Proc()

    monkeypatch.setattr(gbw, "AGENT_RUNNER", runner)
    evidence = {}
    verdict = gbw.run_google_agent_task(
        {"workkey": "WK-MISS-POLICY", "instruction": "do it", "estimated_cost_eur": 0.0},
        tmp_path, evidence, {"has_agy_cli": True},
    )
    assert calls == []
    assert verdict == "FAILED"
    assert evidence.get("provider_invoked") is False
    assert "POLICY_UNAVAILABLE" in evidence.get("blocked_reason", "")


def test_gemini_missing_policy_does_not_spawn(tmp_path, monkeypatch):
    import scripts.gemini_worker_adapter as adapter
    import scripts.resource_policy as policy

    monkeypatch.setattr(policy, "POLICY_FILE", tmp_path / "missing.json")
    task = tmp_path / "task.json"
    task.write_text(json.dumps({
        "task_id": "gemini-miss", "instruction": "echo", "estimated_cost_eur": 0.0,
    }), encoding="utf-8")
    spawned = []

    def popen(*args, **kwargs):
        spawned.append(args)
        raise AssertionError("provider spawned")

    monkeypatch.setattr(adapter.subprocess, "Popen", popen)
    result = adapter.run_worker(str(task))
    assert spawned == []
    assert result["status"] == "FAILED"
    assert result.get("blocked") is True
    assert "POLICY_UNAVAILABLE" in result["reason"]


def test_provider_exec_missing_policy_does_not_launch_agy(tmp_path, monkeypatch):
    import scripts.resource_policy as policy
    from courier_worker.adapters import provider_exec

    monkeypatch.setattr(policy, "POLICY_FILE", tmp_path / "missing.json")
    monkeypatch.setattr(provider_exec, "admit_heavy", lambda: True)
    monkeypatch.delenv("COURIER_PROVIDER_AGY_BIN", raising=False)
    marker = tmp_path / "launched.txt"
    script = tmp_path / "fake_agy.py"
    script.write_text(textwrap.dedent(f"""\
        #!{sys.executable}
        import pathlib
        pathlib.Path({str(marker)!r}).write_text("launched")
        print('{{"provider":"agy","status":"SUCCESS"}}')
        """), encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    workdir = tmp_path / "work"
    workdir.mkdir()
    result = provider_exec.run(
        {"provider": "agy", "prompt": "summarize", "estimated_cost_eur": 0.0},
        workdir,
        config={"binaries": {"agy": str(script)}},
    )
    assert result.launched is False
    assert result.blocked is True
    assert "POLICY_UNAVAILABLE" in result.reason_code
    assert not marker.exists()


def test_provider_exec_blocks_non_finite_and_positive_cost(tmp_path, monkeypatch):
    from courier_worker.adapters import provider_exec

    monkeypatch.setattr(provider_exec, "admit_heavy", lambda: True)
    monkeypatch.delenv("COURIER_PROVIDER_AGY_BIN", raising=False)
    script = tmp_path / "fake_agy.py"
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    workdir = tmp_path / "work"
    workdir.mkdir()
    for cost in (None, float("nan"), float("inf"), float("-inf"), 4.0):
        params = {"provider": "agy", "prompt": "summarize"}
        if cost is not None:
            params["estimated_cost_eur"] = cost
        result = provider_exec.run(params, workdir, config={"binaries": {"agy": str(script)}})
        assert result.launched is False
        assert result.blocked is True


def test_mac_agy_missing_policy_does_not_spawn(tmp_path, monkeypatch):
    pytest.importorskip("fcntl")
    from test_mac_worker_recovery import load_daemon

    daemon = load_daemon(tmp_path, monkeypatch)
    empty = tmp_path / "empty-root"
    empty.mkdir()
    monkeypatch.setattr(daemon, "REPO_ROOT", empty)
    spawned = []
    monkeypatch.setattr(daemon, "admit_surface", lambda *a, **k: spawned.append("admit"))
    monkeypatch.setattr(daemon.shutil, "which", lambda *a, **k: spawned.append("which"))
    monkeypatch.setattr(daemon.subprocess, "Popen", lambda *a, **k: spawned.append("popen"))
    result = daemon.run_agy(
        {"task_id": "t-missing-policy", "instruction": "echo", "estimated_cost_eur": 0.0},
        {"WORKER_ID": "MAC-01", "AGY_TIMEOUT_SECONDS": 5},
    )
    assert result.get("blocked") is True
    assert "POLICY_UNAVAILABLE" in result.get("reason", "")
    assert spawned == []
