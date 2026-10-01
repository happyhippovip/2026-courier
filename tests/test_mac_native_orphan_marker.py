"""run_native orphan marker + restart gate (M2 mac reliability lane).

Proves: run_native persists its child-group identity (native_process.json,
like the muse/agy markers) and marks it CLEAN on success, so a violent
daemon death mid-execution is detectable on restart; require_no_orphan
blocks new claims while a previous native group may still be alive, and
allows them when the group is provably gone.
"""
import importlib.util
import json
import subprocess
from pathlib import Path

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mac_worker" / "daemon.py"


def load_daemon(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("mac_worker_daemon_native_marker", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    (tmp_path / "state").mkdir()
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(daemon, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(daemon, "LOGS_DIR", tmp_path / "logs")
    return daemon


def test_native_marks_clean_on_success(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    result = daemon.run_native({"task_id": "task-native-m-1", "action": "echo",
                                "instruction": "echo hi"},
                               {"WORKER_ID": "MAC-01", "NATIVE_TIMEOUT_SECONDS": 30})
    assert result["status"] == "SUCCESS"
    marker = json.loads((tmp_path / "state" / "native_process.json").read_text())
    assert marker["state"] == "CLEAN"
    assert marker["identity"]["pid"] > 0


def test_require_no_orphan_blocks_live_native_group(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    proc = subprocess.Popen(["sleep", "60"], start_new_session=True)
    try:
        identity = daemon.process_identity(proc.pid)
        assert identity is not None
        daemon.atomic_json(tmp_path / "state" / "native_process.json",
                           {"state": "RUNNING", "identity": identity})
        try:
            daemon.require_no_orphan()
        except RuntimeError:
            blocked = True
        else:
            blocked = False
        assert blocked, "live native group must block new claims/executions"
    finally:
        assert daemon.cleanup_group(proc, identity) is True
        proc.wait()


def test_require_no_orphan_allows_dead_native_group(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    daemon.atomic_json(tmp_path / "state" / "native_process.json",
                       {"state": "RUNNING",
                        "identity": {"pid": 999997, "pgid": 999998, "fingerprint": "dead"}})
    daemon.require_no_orphan()  # provably gone group: no raise
