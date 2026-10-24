"""O7-02 (B1 CostGate): a missing estimate must never be read as 0 EUR.

scripts/windows_worker/daemon.py:359-361 turns ``estimated_cost_eur`` None into
0.0 whenever the task *claims* cost_class included_quota/free/local, so CostGate
(scripts/resource_policy.py:150-158, UNKNOWN_COST=BLOCK) never sees the missing
value and native PowerShell starts. Note: tests/test_windows_costgate_and_writer_lease.py
(task2) currently pins the opposite; WIN-COST-1 v3 changes that test together with the fix.
"""
import pytest

from tests.test_windows_costgate_and_writer_lease import load_daemon


class _Proc:
    pid = 4242
    returncode = 0

    def communicate(self, timeout=None):
        return ("ran", "")


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="O7-02/B1: windows daemon fills a missing estimate with 0.0 from cost_class")
@pytest.mark.parametrize("cost_class", ["included_quota", "free", "local"])
def test_missing_estimate_with_a_cost_class_claim_is_blocked_before_powershell(tmp_path, monkeypatch, cost_class):
    daemon = load_daemon(tmp_path, monkeypatch)
    started = []
    monkeypatch.setattr(daemon.subprocess, "Popen", lambda *a, **k: started.append(a) or _Proc())
    task = {"task_id": "o7-02", "instruction": "Write-Host ok", "cost_class": cost_class}
    result = daemon.run_task(task, {"WORKER_ID": "WIN-O7"})
    assert started == []
    assert result.get("blocked") is True
    assert "UNKNOWN_COST" in result.get("stderr", "")


@pytest.mark.parametrize("estimate", [None, ""])
def test_guard_missing_or_empty_estimate_without_class_is_blocked(tmp_path, monkeypatch, estimate):
    """Guard that already holds on the base: no class, None/empty estimate -> UNKNOWN_COST."""
    daemon = load_daemon(tmp_path, monkeypatch)
    started = []
    monkeypatch.setattr(daemon.subprocess, "Popen", lambda *a, **k: started.append(a) or _Proc())
    result = daemon.run_task({"task_id": "o7-02g", "instruction": "dir", "estimated_cost_eur": estimate},
                             {"WORKER_ID": "WIN-O7"})
    assert started == [] and result.get("blocked") is True and "UNKNOWN_COST" in result["stderr"]
