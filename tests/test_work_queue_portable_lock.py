"""Portable-lock regression: work_queue must not depend on fcntl (Windows).

Simulates Windows by making fcntl unimportable, then runs a full
claim -> complete -> reconcile cycle against a tmp state dir.
"""
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).parent.parent.resolve()
WQ = REPO / "scripts" / "work_queue.py"


def load_no_fcntl():
    assert "fcntl" not in sys.modules or sys.modules["fcntl"] is None
    spec = importlib.util.spec_from_file_location("wq_no_fcntl", WQ)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_no_fcntl_dependency(monkeypatch):
    monkeypatch.setitem(sys.modules, "fcntl", None)
    for mod in [m for m in list(sys.modules) if m == "wq_no_fcntl"]:
        del sys.modules[mod]
    load_no_fcntl()  # must import without fcntl


def _q(*args, state_dir):
    r = subprocess.run(
        [sys.executable, str(WQ), "--state-dir", str(state_dir)] + list(args),
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return json.loads(r.stdout.strip())


def test_full_cycle_without_fcntl(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "fcntl", None)
    sd = str(tmp_path / "q")
    _q("init", "P", "--dod", "smoke", state_dir=sd)
    _q("add", json.dumps({"task_id": "T1", "package_id": "P",
        "description": "t", "required_capabilities": [],
        "dependencies": [], "read_scopes": [], "write_scopes": [],
        "risk": "none", "status": "READY", "owner": "", "priority": 1}),
        state_dir=sd)
    assert _q("claim", "--worker", "w", "--package", "P",
              state_dir=sd)["claimed"] == "T1"
    out = _q("complete", "T1", "--result-json",
             json.dumps({"result_id": "T1:r1"}), "--stage", "ACCEPTED",
             state_dir=sd)
    assert out["done"] == "T1"
    st = _q("state", state_dir=sd)
    assert st["tasks"]["T1"]["status"] == "DONE"


def test_stale_lock_recovery(tmp_path):
    sd = str(tmp_path / "q")
    _q("init", "P", state_dir=sd)

    # Simulate a crashed process that left a lockdir with a dead PID
    lockdir = Path(sd) / "queue.json.lockdir"
    lockdir.mkdir(parents=True, exist_ok=True)
    owner_file = lockdir / "owner.json"
    owner_file.write_text(json.dumps({"pid": 99999999, "time": time.time() - 100}), encoding="utf-8")

    # Subsequent operation detects dead PID, unlinks stale lock, and proceeds
    res = _q("add", json.dumps({"task_id": "T1", "package_id": "P",
        "description": "t", "dependencies": [], "read_scopes": [], "write_scopes": [],
        "status": "READY"}), state_dir=sd)
    assert res["added"] == "T1"


def test_state_does_not_rewrite_file(tmp_path):
    sd = str(tmp_path / "q")
    _q("init", "P", state_dir=sd)
    qf = Path(sd) / "queue.json"
    mtime_before = qf.stat().st_mtime_ns
    time.sleep(0.05)
    st = _q("state", state_dir=sd)
    assert "tasks" in st
    mtime_after = qf.stat().st_mtime_ns
    assert mtime_before == mtime_after
