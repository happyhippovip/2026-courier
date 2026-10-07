"""Mac worker surface admission: coalesced work is never reported as a success,
and a real agy/muse run is bound to its (pid, create_time) surface."""
import sys
import pytest

if sys.platform == 'win32':
    pytest.skip('Mac worker admission tests require Unix (fcntl)', allow_module_level=True)

import importlib.util
from pathlib import Path

from courier_runtime.surfaces import Decision

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mac_worker" / "daemon.py"


def load_daemon(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("mac_worker_daemon_admission", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    for name in ("state", "logs"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(daemon, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(daemon, "LOGS_DIR", tmp_path / "logs")
    return daemon


def test_coalesced_agy_task_is_not_a_success(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    monkeypatch.setattr(daemon, "admit_surface",
                        lambda *a, **k: (None, Decision("COALESCED", "mac-s1", "same intent", "k", 3)))
    result = daemon.run_agy({"task_id": "T1", "instruction": "x"}, {"WORKER_ID": "mac-1"})
    assert result["status"] == "FAILED" and result["reason"] == "COALESCED_INTO_RUNNING_WORK"


def test_attach_surface_uses_real_process_identity(tmp_path, monkeypatch):
    import os

    import psutil
    daemon = load_daemon(tmp_path, monkeypatch)
    seen = {}

    class Sup:
        def attach(self, sid, pid, create_time):
            seen.update(sid=sid, pid=pid, create_time=create_time)

    daemon.attach_surface(Sup(), Decision("OPEN", "mac-s2"), os.getpid())
    assert seen == {"sid": "mac-s2", "pid": os.getpid(), "create_time": psutil.Process(os.getpid()).create_time()}
    daemon.attach_surface(Sup(), Decision("OPEN", "mac-s3"), 999999)      # gone pid: logged, not raised
