"""adapter_runner: provider_exec is allowlisted but fail-closed behind a cost gate.

No real provider binary is ever launched: provider_exec.run is replaced by a mock.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from courier_worker import adapter_runner  # noqa: E402
from courier_worker.adapters import provider_exec  # noqa: E402

RUNNER = ROOT / "courier_worker" / "adapter_runner.py"
GOOD_GATE = {"approved": True, "estimated_cost_eur": 0.0, "max_cost_eur": 1.0, "approval_ref": "TEST-MOCK"}


def _request(tmp_path, adapter, params, **extra):
    req = {"adapter": adapter, "workdir": str(tmp_path / "wd"), "report": str(tmp_path / "out" / "r.json"),
           "attempt": 1, "params": params, **extra}
    path = tmp_path / "req.json"
    path.write_text(json.dumps(req))
    return path, Path(req["report"])


@pytest.fixture
def no_launch(monkeypatch):
    calls = []

    def fake_run(params, workdir, attempt=1, *, config=None):
        calls.append(params)
        out = b"mock ok"
        import hashlib
        return provider_exec.ProviderResult(outcome="success", output=out, launched=True,
                                            output_sha256=hashlib.sha256(out).hexdigest())

    monkeypatch.setattr(provider_exec, "run", fake_run)
    return calls


def test_provider_exec_is_allowlisted():
    assert "provider_exec" in adapter_runner.ALLOWED and "synthetic" in adapter_runner.ALLOWED


def test_synthetic_still_green(tmp_path):
    path, report = _request(tmp_path, "synthetic", {})
    proc = subprocess.run([sys.executable, str(RUNNER), str(path)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(report.read_text())["outcome"]


def test_unknown_adapter_still_rejected(tmp_path):
    path, report = _request(tmp_path, "local_shell", {})
    assert adapter_runner.main([str(path)]) == 2
    assert not report.exists()


def test_without_cost_gate_rejected_by_default(tmp_path, monkeypatch, no_launch):
    monkeypatch.delenv(adapter_runner.COST_GATE_ENV, raising=False)
    path, report = _request(tmp_path, "provider_exec", {"provider": "muse", "prompt": "x"}, cost_gate=GOOD_GATE)
    assert adapter_runner.main([str(path)]) == 0
    rep = json.loads(report.read_text())
    assert rep == {"outcome": "rejected", "reason": "COST_GATE_CLOSED", "retryable": False, "launched": False}
    assert no_launch == []


def test_subprocess_default_gate_closed_never_launches(tmp_path, monkeypatch):
    monkeypatch.delenv(adapter_runner.COST_GATE_ENV, raising=False)
    path, report = _request(tmp_path, "provider_exec", {"provider": "muse", "prompt": "x"})
    env = {k: v for k, v in __import__("os").environ.items() if k != adapter_runner.COST_GATE_ENV}
    proc = subprocess.run([sys.executable, str(RUNNER), str(path)], capture_output=True, text=True,
                          timeout=60, env=env)
    assert proc.returncode == 0
    assert "COST_GATE_CLOSED" in proc.stderr
    assert json.loads(report.read_text())["launched"] is False


@pytest.mark.parametrize("gate,code", [
    (None, "COST_GATE_MISSING"),
    ({**GOOD_GATE, "approved": False}, "COST_GATE_NOT_APPROVED"),
    ({**GOOD_GATE, "approved": "yes"}, "COST_GATE_NOT_APPROVED"),
    ({**GOOD_GATE, "approval_ref": ""}, "COST_GATE_NO_EVIDENCE"),
    ({k: v for k, v in GOOD_GATE.items() if k != "estimated_cost_eur"}, "COST_GATE_UNKNOWN_COST"),
    ({**GOOD_GATE, "estimated_cost_eur": None}, "COST_GATE_UNKNOWN_COST"),
    ({**GOOD_GATE, "estimated_cost_eur": "0"}, "COST_GATE_UNKNOWN_COST"),
    ({**GOOD_GATE, "estimated_cost_eur": float("nan")}, "COST_GATE_UNKNOWN_COST"),
    ({**GOOD_GATE, "estimated_cost_eur": -1}, "COST_GATE_UNKNOWN_COST"),
    ({**GOOD_GATE, "max_cost_eur": None}, "COST_GATE_UNKNOWN_COST"),
    ({**GOOD_GATE, "estimated_cost_eur": 2.0}, "COST_GATE_OVER_BUDGET"),
])
def test_fail_closed_cases(tmp_path, monkeypatch, no_launch, gate, code):
    monkeypatch.setenv(adapter_runner.COST_GATE_ENV, "open")
    extra = {} if gate is None else {"cost_gate": gate}
    path, report = _request(tmp_path, "provider_exec", {"provider": "muse", "prompt": "x"}, **extra)
    assert adapter_runner.main([str(path)]) == 0
    rep = json.loads(report.read_text())
    assert rep["outcome"] == "rejected" and rep["reason"] == code and rep["launched"] is False
    assert no_launch == []


def test_env_must_be_exactly_open(monkeypatch):
    monkeypatch.setenv(adapter_runner.COST_GATE_ENV, "1")
    assert adapter_runner.check_cost_gate({"cost_gate": GOOD_GATE}) == "COST_GATE_CLOSED"


def test_with_gate_mock_runs_through(tmp_path, monkeypatch, no_launch):
    monkeypatch.setenv(adapter_runner.COST_GATE_ENV, "open")
    path, report = _request(tmp_path, "provider_exec", {"provider": "muse", "prompt": "x"}, cost_gate=GOOD_GATE)
    assert adapter_runner.main([str(path)]) == 0
    rep = json.loads(report.read_text())
    assert rep["outcome"] == "success" and rep["launched"] is True and rep["verified"] is True
    assert "output_sha256=" in rep["reason"]
    assert no_launch == [{"provider": "muse", "prompt": "x"}]


def test_gate_open_but_adapter_rejects_reports_cleanly(tmp_path, monkeypatch):
    # Real provider_exec.run with no binary configured: must not launch anything.
    monkeypatch.setenv(adapter_runner.COST_GATE_ENV, "open")
    monkeypatch.delenv("COURIER_PROVIDER_MUSE_BIN", raising=False)
    path, report = _request(tmp_path, "provider_exec", {"provider": "muse", "prompt": "x"}, cost_gate=GOOD_GATE)
    assert adapter_runner.main([str(path)]) == 0
    rep = json.loads(report.read_text())
    assert rep["outcome"] != "success" and rep["launched"] is False
