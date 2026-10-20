"""P0: a provider start asks CostGate with the caller's estimate.

Muse has no active policy entry, so an explicit free run is still refused.
A missing estimate is not rewritten to 0.0. A CostGate error refuses the launch.
Providers are fakes; nothing here proves a real provider run.
"""
import stat
import sys
import textwrap
from pathlib import Path

import pytest

from courier_worker.adapters import provider_exec
from scripts.resource_policy import CostGate


@pytest.fixture(autouse=True)
def _admit_heavy(monkeypatch):
    monkeypatch.setattr(provider_exec, "admit_heavy", lambda: True)


def _fake_muse(tmp_path, marker):
    script = tmp_path / "fake_muse.py"
    script.write_text(textwrap.dedent(f"""\
        #!{sys.executable}
        import pathlib
        pathlib.Path({str(marker)!r}).write_text("launched")
        print("provider-ok")
        """), encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def _run_muse(tmp_path, monkeypatch, *, estimated_cost_eur=0.0, include_cost=True):
    marker = tmp_path / "launched.txt"
    monkeypatch.delenv("COURIER_PROVIDER_MUSE_BIN", raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    params = {"provider": "muse", "prompt": "summarize"}
    if include_cost:
        params["estimated_cost_eur"] = estimated_cost_eur
    result = provider_exec.run(
        params, workdir, config={"binaries": {"muse": _fake_muse(tmp_path, marker)}},
    )
    return result, marker


def test_provider_exec_refuses_muse_without_active_policy_entry(tmp_path, monkeypatch):
    result, marker = _run_muse(tmp_path, monkeypatch)
    assert result.launched is False
    assert result.reason_code == "COST_GATE_UNAUTHORIZED_RESOURCE_TIER"
    assert not marker.exists()


def test_missing_estimate_is_not_sent_as_zero(tmp_path, monkeypatch):
    seen = []
    original = CostGate.evaluate_spend_request

    def spy(*args, **kwargs):
        seen.append(kwargs.get("estimated_cost_eur"))
        return original(*args, **kwargs)

    monkeypatch.setattr(CostGate, "evaluate_spend_request", staticmethod(spy))
    result, marker = _run_muse(tmp_path, monkeypatch, include_cost=False)
    assert result.launched is False
    assert result.reason_code == "UNKNOWN_COST_BLOCKED"
    assert 0.0 not in seen
    assert not marker.exists()


def test_explicit_zero_is_the_value_the_gate_sees(tmp_path, monkeypatch):
    seen = []
    original = CostGate.evaluate_spend_request

    def spy(*args, **kwargs):
        seen.append((args[0], kwargs.get("estimated_cost_eur")))
        return original(*args, **kwargs)

    monkeypatch.setattr(CostGate, "evaluate_spend_request", staticmethod(spy))
    result, marker = _run_muse(tmp_path, monkeypatch, estimated_cost_eur=0.0)
    assert result.reason_code == "COST_GATE_UNAUTHORIZED_RESOURCE_TIER"
    assert seen == [("muse_subscription", 0.0)]
    assert not marker.exists()


def test_provider_exec_refuses_when_cost_gate_denies(tmp_path, monkeypatch):
    monkeypatch.setattr(
        CostGate, "evaluate_spend_request",
        staticmethod(lambda *a, **k: {"allowed": False, "reason": "UNKNOWN_COST"}),
    )
    result, marker = _run_muse(tmp_path, monkeypatch)
    assert result.launched is False
    assert result.reason_code == "COST_GATE_UNKNOWN_COST"
    assert not marker.exists()


def test_provider_exec_cost_gate_error_fails_closed(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("policy unreadable")

    monkeypatch.setattr(CostGate, "evaluate_spend_request", staticmethod(boom))
    result, marker = _run_muse(tmp_path, monkeypatch)
    assert result.launched is False
    assert result.reason_code == "COST_GATE_UNAVAILABLE"
    assert not marker.exists()


def test_provider_exec_admits_agy_only_for_an_explicit_zero():
    assert provider_exec.admit_cost("agy") == "COST_GATE_UNKNOWN_COST"
    assert provider_exec.admit_cost("agy", None) == "COST_GATE_UNKNOWN_COST"
    assert provider_exec.admit_cost("agy", 0.0) is None
