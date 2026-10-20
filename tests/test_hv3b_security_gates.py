"""HV3-B: the Google builder never skips permissions, and unknown cost stays blocked.

The Mac worker is outside this change. The provider is a recorder, so this
proves Courier-side control flow only.
"""
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.google_builder_worker as gbw
from courier_core.work_packet import PacketState, WorkPacket
from scripts.resource_policy import CostGate
from scripts.run_antigravity_bridge import AntigravityHookRunner, AntigravityVisualStateTracker

ROOT = Path(__file__).resolve().parents[1]
BYPASS_FLAG = "--dangerously-skip-permissions"
SHA = "f425d3285611333d81cfffa263deebba186e398c"
SURFACE_OK = {"has_agy_cli": True, "authorized_mode": "CLI_ONLY"}
OK_VERIFY = [sys.executable, "-c", "import sys; sys.exit(0)"]
DENY = {"allowed": False, "reason": "UNKNOWN_COST", "message": "test", "requires_human_gate": True}


class RecordingRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout='{"result":"done"}', stderr="")


def _packet(**extra):
    payload = {
        "task_type": "google_agent_execute",
        "workkey": "WK-HV3B",
        "instruction": "Add a docstring to foo()",
        "verify_command": OK_VERIFY,
        "estimated_cost_eur": 0.0,
    }
    payload.update(extra)
    return WorkPacket(
        id="pkt-hv3b", owner_id="google-mac", target_sha=SHA,
        state=PacketState.CURRENT, payload=payload,
    )


def _hooks(tmp_path):
    return AntigravityHookRunner(AntigravityVisualStateTracker(repo_dir=tmp_path))


def test_google_builder_argv_never_skips_permissions(tmp_path, monkeypatch):
    runner = RecordingRunner()
    monkeypatch.setattr(gbw, "AGENT_RUNNER", runner)
    gbw.execute_packet_code_or_test_work(_packet(), tmp_path, _hooks(tmp_path), SURFACE_OK)
    assert len(runner.calls) == 1
    argv, _kwargs = runner.calls[0]
    assert BYPASS_FLAG not in argv
    assert "--sandbox" in argv


@pytest.mark.parametrize("cost", [None, math.nan, math.inf, -1.0, "0", True])
def test_cost_gate_blocks_unknown_cost(cost):
    if cost is None:
        res = CostGate.evaluate_spend_request("google_antigravity_plus")
    else:
        res = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=cost)
    assert res["allowed"] is False
    assert res["reason"] == "UNKNOWN_COST"


def test_cost_gate_allows_known_zero_cost_on_active_resource():
    res = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=0.0)
    assert res["allowed"] is True


def test_google_builder_cost_gate_denial_never_invokes_provider(tmp_path, monkeypatch):
    runner = RecordingRunner()
    monkeypatch.setattr(gbw, "AGENT_RUNNER", runner)
    monkeypatch.setattr(CostGate, "evaluate_spend_request", staticmethod(lambda *a, **k: dict(DENY)))
    res = gbw.execute_packet_code_or_test_work(_packet(), tmp_path, _hooks(tmp_path), SURFACE_OK)
    assert runner.calls == []
    assert res["verdict"] == "FAILED"


def test_google_builder_missing_cost_never_invokes_provider(tmp_path, monkeypatch):
    runner = RecordingRunner()
    monkeypatch.setattr(gbw, "AGENT_RUNNER", runner)
    res = gbw.execute_packet_code_or_test_work(
        _packet(estimated_cost_eur=None), tmp_path, _hooks(tmp_path), SURFACE_OK,
    )
    assert runner.calls == []
    assert res["verdict"] == "FAILED"


def test_no_bypass_flag_outside_the_deny_list():
    allowed = {ROOT / "courier_worker" / "adapters" / "provider_exec.py"}
    skipped = {"tests", "attic", ".git", "node_modules", "__pycache__"}
    hits = []
    for path in ROOT.rglob("*"):
        if path.suffix not in (".py", ".sh") or not path.is_file() or path in allowed:
            continue
        if skipped.intersection(path.relative_to(ROOT).parts):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            code = line.split("#", 1)[0]
            if BYPASS_FLAG in code:
                hits.append(f"{path.relative_to(ROOT)}:{number}")
    assert hits == []
