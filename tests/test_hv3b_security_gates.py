"""HV3-B: no permission bypass on the agy paths, and a cost gate that fails closed.

- mac_worker daemon.run_agy and the Google builder never pass
  --dangerously-skip-permissions to agy.
- CostGate refuses a spend request whose cost is missing or is not a finite
  number >= 0 (UNKNOWN_COST=BLOCK).
- Both agy paths ask CostGate before the provider starts; a denial means no
  process is spawned.
- No executable file outside the provider_exec deny lists carries the flag.

The provider is replaced by recorders, so these tests prove Courier-side
control flow only. They are not evidence of a real agy run.
"""
import importlib.util
import math
import os
import stat
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.google_builder_worker as gbw
from courier_core.work_packet import PacketState, WorkPacket
from scripts.resource_policy import CostGate
from scripts.run_antigravity_bridge import AntigravityHookRunner, AntigravityVisualStateTracker

ROOT = Path(__file__).resolve().parents[1]
DAEMON_PATH = ROOT / "scripts" / "mac_worker" / "daemon.py"
# scripts/mac_worker is POSIX-only (runtime_state imports fcntl); L1 CI policy
# runs it on Linux and macOS only.
POSIX_ONLY = pytest.mark.skipif(importlib.util.find_spec("fcntl") is None,
                                reason="scripts/mac_worker imports the POSIX-only fcntl module")
BYPASS_FLAG = "--dangerously-skip-permissions"
SHA = "f425d3285611333d81cfffa263deebba186e398c"
SURFACE_OK = {"has_agy_cli": True, "authorized_mode": "CLI_ONLY"}
OK_VERIFY = [sys.executable, "-c", "import sys; sys.exit(0)"]
DENY = {"allowed": False, "reason": "UNKNOWN_COST", "message": "test", "requires_human_gate": True}


def load_daemon(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("mac_worker_daemon_hv3b", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    (tmp_path / "state").mkdir()
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(daemon, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(daemon, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(daemon.time, "sleep", lambda seconds: None)
    return daemon


def fake_agy_on_path(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    agy = bindir / "agy"
    agy.write_text("#!/bin/sh\nexit 0\n")
    agy.chmod(agy.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))


def recording_subprocess(instances):
    real = subprocess.Popen

    class RecordingPopen(real):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            instances.append(self)

    return types.SimpleNamespace(PIPE=subprocess.PIPE, DEVNULL=subprocess.DEVNULL,
                                 TimeoutExpired=subprocess.TimeoutExpired, Popen=RecordingPopen)


class RecordingRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout='{"result":"done"}', stderr="")


def _packet():
    return WorkPacket(id="pkt-hv3b", owner_id="google-mac", target_sha=SHA, state=PacketState.CURRENT,
                      payload={"task_type": "google_agent_execute", "workkey": "WK-HV3B",
                               "instruction": "Add a docstring to foo()", "verify_command": OK_VERIFY,
                               "estimated_cost_eur": 0.0})


def _hooks(tmp_path):
    return AntigravityHookRunner(AntigravityVisualStateTracker(repo_dir=tmp_path))


@POSIX_ONLY
def test_daemon_agy_argv_never_skips_permissions(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    fake_agy_on_path(tmp_path, monkeypatch)
    instances = []
    monkeypatch.setattr(daemon, "subprocess", recording_subprocess(instances))
    daemon.run_agy({"task_id": "task-hv3b-1", "instruction": "do work", "estimated_cost_eur": 0.0}, {"AGY_TIMEOUT_SECONDS": 5})
    assert len(instances) == 1
    assert BYPASS_FLAG not in instances[0].args


def test_google_builder_argv_never_skips_permissions(tmp_path, monkeypatch):
    runner = RecordingRunner()
    monkeypatch.setattr(gbw, "AGENT_RUNNER", runner)
    gbw.execute_packet_code_or_test_work(_packet(), tmp_path, _hooks(tmp_path), SURFACE_OK)
    assert len(runner.calls) == 1
    argv, _ = runner.calls[0]
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


@POSIX_ONLY
def test_daemon_cost_gate_denial_spawns_nothing(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    fake_agy_on_path(tmp_path, monkeypatch)
    instances = []
    monkeypatch.setattr(daemon, "subprocess", recording_subprocess(instances))
    monkeypatch.setattr(daemon, "cost_gate", lambda resource_id: dict(DENY))
    result = daemon.run_agy({"task_id": "task-hv3b-2", "instruction": "do work"}, {"AGY_TIMEOUT_SECONDS": 5})
    assert instances == []
    assert result["status"] == "FAILED"
    assert "COST_GATE" in result["reason"] and "UNKNOWN_COST" in result["reason"]


def test_google_builder_cost_gate_denial_never_invokes_provider(tmp_path, monkeypatch):
    runner = RecordingRunner()
    monkeypatch.setattr(gbw, "AGENT_RUNNER", runner)
    # The builder imports CostGate lazily from scripts.resource_policy, so patch the class itself.
    monkeypatch.setattr(CostGate, "evaluate_spend_request", staticmethod(lambda *a, **k: dict(DENY)))
    res = gbw.execute_packet_code_or_test_work(_packet(), tmp_path, _hooks(tmp_path), SURFACE_OK)
    assert runner.calls == []
    assert res["verdict"] == "FAILED"


def test_no_bypass_flag_in_executable_paths():
    allowed = {
        ROOT / "courier_worker" / "adapters" / "provider_exec.py",
        ROOT / "adapters" / "local_shell.py",
        ROOT / "scripts" / "google_builder_worker.py",
    }  # deny lists only
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
