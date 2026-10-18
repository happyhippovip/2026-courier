"""P0: UNKNOWN_COST=BLOCK on every provider start path, and no --yolo.

- provider_exec.run asks CostGate before a launch. Muse has no active entry in
  the resource policy, so it is refused until a human adds one.
- A CostGate error refuses the launch (fail closed).
- mac_worker daemon.run_muse asks CostGate before Popen and refuses --yolo.
- muse_adapter never builds a command with --yolo.
- No executable file outside the provider_exec deny lists appends --yolo.

Providers are fakes; nothing here proves a real provider run.
"""
import importlib.util
import stat
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from courier_worker.adapters import provider_exec
from scripts.resource_policy import CostGate

ROOT = Path(__file__).resolve().parents[1]
DAEMON_PATH = ROOT / "scripts" / "mac_worker" / "daemon.py"
sys.path.insert(0, str(ROOT / "scripts" / "mac_worker"))
import muse_adapter  # noqa: E402


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


def _run_muse_provider(tmp_path, monkeypatch):
    marker = tmp_path / "launched.txt"
    monkeypatch.delenv("COURIER_PROVIDER_MUSE_BIN", raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    result = provider_exec.run({"provider": "muse", "prompt": "summarize"}, workdir,
                               config={"binaries": {"muse": _fake_muse(tmp_path, marker)}})
    return result, marker


def test_provider_exec_refuses_muse_without_active_policy_entry(tmp_path, monkeypatch):
    result, marker = _run_muse_provider(tmp_path, monkeypatch)
    assert result.launched is False
    assert result.reason_code == "COST_GATE_UNAUTHORIZED_RESOURCE_TIER"
    assert not marker.exists()


def test_provider_exec_refuses_when_cost_gate_denies(tmp_path, monkeypatch):
    monkeypatch.setattr(CostGate, "evaluate_spend_request",
                        staticmethod(lambda *a, **k: {"allowed": False, "reason": "UNKNOWN_COST"}))
    result, marker = _run_muse_provider(tmp_path, monkeypatch)
    assert result.launched is False
    assert result.reason_code == "COST_GATE_UNKNOWN_COST"
    assert not marker.exists()


def test_provider_exec_cost_gate_error_fails_closed(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("policy unreadable")
    monkeypatch.setattr(CostGate, "evaluate_spend_request", staticmethod(boom))
    result, marker = _run_muse_provider(tmp_path, monkeypatch)
    assert result.launched is False
    assert result.reason_code == "COST_GATE_UNAVAILABLE"
    assert not marker.exists()


def test_provider_exec_admits_agy_resource():
    assert provider_exec.admit_cost("agy") is None


MUSE_TASK = {"goal_id": "g-p0", "task_id": "t-p0", "attempt_id": "a-1", "dispatch_id": "d-1",
             "instruction": "x", "mode": "MUSE"}


def _load_daemon(tmp_path, monkeypatch):
    """Everything before Popen is stubbed open, so without a gate Muse would start."""
    spec = importlib.util.spec_from_file_location("mac_worker_daemon_p0", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    (tmp_path / "state").mkdir()
    (tmp_path / "logs").mkdir()
    (tmp_path / "ws").mkdir()
    monkeypatch.setattr(daemon, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(daemon, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(daemon, "admit_surface",
                        lambda *a, **k: (None, SimpleNamespace(action="LAUNCH")))
    monkeypatch.setattr(daemon, "require_no_orphan", lambda: None)
    monkeypatch.setattr(daemon, "resource_ready", lambda: True)
    monkeypatch.setattr(daemon, "stopped", lambda: False)
    monkeypatch.setenv("COURIER_MUSE_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("COURIER_MUSE_CLI", '{"protocol": "headless-v1"}')
    launched = []

    def no_popen(*a, **k):
        launched.append(a)
        raise AssertionError("Muse must not start")
    monkeypatch.setattr(daemon.subprocess, "Popen", no_popen)
    return daemon, launched


def _call_run_muse(daemon):
    try:
        return daemon.run_muse(dict(MUSE_TASK), {"WORKER_ID": "MAC-01"})
    except Exception as exc:  # the unpatched path dies inside the launch block
        return {"status": "RAISED", "reason": type(exc).__name__}


def test_daemon_run_muse_refused_by_cost_gate(tmp_path, monkeypatch):
    daemon, launched = _load_daemon(tmp_path, monkeypatch)
    result = _call_run_muse(daemon)
    assert launched == []
    assert result["status"] == "FAILED"
    assert result["reason"] == "COST_GATE_UNAUTHORIZED_RESOURCE_TIER"


def test_daemon_run_muse_refuses_yolo(tmp_path, monkeypatch):
    daemon, launched = _load_daemon(tmp_path, monkeypatch)
    monkeypatch.setattr(daemon, "cost_gate", lambda resource_id: {"allowed": True}, raising=False)
    monkeypatch.setenv("COURIER_MUSE_CLI", '{"protocol": "headless-v1", "yolo": true}')
    result = _call_run_muse(daemon)
    assert launched == []
    assert result["status"] == "FAILED"
    assert result["reason"] == "YOLO_NOT_ALLOWED"


def test_muse_adapter_never_builds_yolo():
    task = {"task_id": "t-p0-3", "attempt": 1, "dispatch_id": "d-1"}
    with pytest.raises(muse_adapter.MuseCapabilityUnknown):
        muse_adapter.build_muse_command(task, {}, {"protocol": "headless-v1", "yolo": True},
                                        slot_id="MAC-01", workspace="/tmp/ws", action="exec", prompt="p")


def test_no_yolo_appended_in_executable_paths():
    allowed = {ROOT / "courier_worker" / "adapters" / "provider_exec.py"}  # deny lists only
    skipped = {"tests", "attic", ".git", "node_modules", "__pycache__"}
    hits = []
    for path in ROOT.rglob("*.py"):
        if path in allowed or skipped.intersection(path.relative_to(ROOT).parts):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            code = line.split("#", 1)[0]
            if '"--yolo"' in code and "append" in code:
                hits.append(f"{path.relative_to(ROOT)}:{number}")
    assert hits == []
