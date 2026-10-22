"""Mac worker daemon must not run on a file lock alone."""

import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("fcntl")

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mac_worker" / "daemon.py"


def load_daemon(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("mac_worker_daemon_lease", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    state = tmp_path / "state"
    logs = tmp_path / "logs"
    state.mkdir()
    logs.mkdir()
    monkeypatch.setattr(daemon, "STATE_DIR", state)
    monkeypatch.setattr(daemon, "LOGS_DIR", logs)
    return daemon


def _other_process_can_lock(path: Path) -> bool:
    script = textwrap.dedent(
        """
        import fcntl, sys
        handle = open(sys.argv[1], "a")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SystemExit(3)
        raise SystemExit(0)
        """
    )
    result = subprocess.run([sys.executable, "-c", script, str(path)], check=False)
    return result.returncode == 0


def test_missing_store_releases_the_file_lock(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    original = daemon.get_authority_store
    monkeypatch.setattr(daemon, "get_authority_store", lambda: None)
    with pytest.raises(RuntimeError, match="refusing to run without a writer lease"):
        daemon.acquire_worker_lock()
    assert daemon._worker_lock_handle is None
    assert daemon._worker_lease is None
    lock_path = tmp_path / "state" / "worker.lock"
    assert _other_process_can_lock(lock_path)

    monkeypatch.setattr(daemon, "get_authority_store", original)
    handle = daemon.acquire_worker_lock()
    assert handle is not None
    assert daemon._worker_lease is not None
    assert _other_process_can_lock(lock_path) is False
    daemon.release_worker_lock(handle)
    assert daemon._worker_lease is None
    assert _other_process_can_lock(lock_path)


def test_lease_conflict_releases_the_file_lock(tmp_path, monkeypatch):
    from courier_runtime.lease import LeaseConflict

    daemon = load_daemon(tmp_path, monkeypatch)

    class Held:
        def acquire(self, *_args, **_kwargs):
            raise LeaseConflict("worker scope is held")

    monkeypatch.setattr(daemon, "get_authority_store", lambda: Held())
    assert daemon.acquire_worker_lock() is None
    assert daemon._worker_lease is None
    assert daemon._worker_lock_handle is None
    assert _other_process_can_lock(tmp_path / "state" / "worker.lock")


def test_authority_error_releases_the_file_lock(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)

    class Broken:
        def acquire(self, *_args, **_kwargs):
            raise RuntimeError("authority.db unreadable")

    monkeypatch.setattr(daemon, "get_authority_store", lambda: Broken())
    with pytest.raises(RuntimeError, match="authority.db unreadable"):
        daemon.acquire_worker_lock()
    assert daemon._worker_lock_handle is None
    assert daemon._worker_lease is None
    assert _other_process_can_lock(tmp_path / "state" / "worker.lock")


def test_acquire_records_authority_lease(tmp_path, monkeypatch):
    from courier_runtime.lease import LeaseStore

    daemon = load_daemon(tmp_path, monkeypatch)
    handle = daemon.acquire_worker_lock()
    try:
        store = LeaseStore(str(tmp_path / "state" / "authority.db"))
        lease = store.current("worker:mac")
        store.close()
        assert lease is not None
        assert lease.workkey == "daemon_loop"
        assert str(lease.holder).startswith("mac_worker:")
    finally:
        daemon.release_worker_lock(handle)
    store = LeaseStore(str(tmp_path / "state" / "authority.db"))
    try:
        assert store.current("worker:mac") is None
    finally:
        store.close()
