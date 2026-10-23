"""A lock that cannot be created is a failed start, not a second instance."""
import sys
import types

import pytest

from tests.test_windows_worker_contract import load_daemon


def test_missing_lock_file_is_not_another_instance(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)

    def boom(*_args, **_kwargs):
        raise FileNotFoundError("temp missing")

    monkeypatch.setattr(daemon.os, "open", boom)
    with pytest.raises(FileNotFoundError):
        daemon.acquire_lock("WIN-01")


def test_loop_does_not_exit_clean_when_the_lock_cannot_be_created(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)

    def boom(*_args, **_kwargs):
        raise FileNotFoundError("temp missing")

    monkeypatch.setattr(daemon.os, "open", boom)
    with pytest.raises(FileNotFoundError):
        daemon.loop()


def test_missing_lock_module_is_not_another_instance(tmp_path, monkeypatch):
    """A Windows host without msvcrt must fail the start, not exit as a duplicate."""
    daemon = load_daemon(tmp_path, monkeypatch)
    monkeypatch.setitem(sys.modules, "msvcrt", None)
    with pytest.raises(ImportError):
        daemon.acquire_lock("WIN-LOCK")


def test_unopenable_lease_store_does_not_run_on_the_file_lock(tmp_path, monkeypatch):
    """A file lock without a canonical lease must not start the worker."""
    daemon = load_daemon(tmp_path, monkeypatch)
    database = daemon.STATE_DIR / "authority.db"
    database.write_bytes(b"this is not a sqlite database")
    with pytest.raises(RuntimeError, match="canonical writer lease"):
        daemon.acquire_lock("WIN-LEASE")
    assert daemon._lock_fd is None
    assert daemon._worker_lease is None


def test_loop_does_not_exit_clean_when_the_lease_store_is_unreadable(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    (daemon.STATE_DIR / "authority.db").write_bytes(b"this is not a sqlite database")
    with pytest.raises(RuntimeError, match="canonical writer lease"):
        daemon.loop()


def test_foreign_lease_does_not_start_the_daemon(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    store = daemon.get_authority_store()
    store.acquire("worker:WIN-LEASE", "other-host", "other-work", ttl_s=3600)
    with pytest.raises(RuntimeError, match="canonical writer lease"):
        daemon.acquire_lock("WIN-LEASE")
    assert daemon._lock_fd is None


def test_dead_holder_lease_is_taken_over(tmp_path, monkeypatch):
    from courier_runtime.lease import format_session_holder

    daemon = load_daemon(tmp_path, monkeypatch)
    store = daemon.get_authority_store()
    dead = format_session_holder("WIN-LEASE", 2**30, 1.0, "dead-session")
    store.acquire("worker:WIN-LEASE", dead, "daemon_loop", ttl_s=3600)
    lock_path = daemon.acquire_lock("WIN-LEASE")
    try:
        assert daemon._worker_lease is not None
        assert daemon._worker_lease.holder != dead
    finally:
        daemon.release_lock(lock_path)


def test_live_holder_blocks_a_second_start(tmp_path, monkeypatch):
    import psutil
    from courier_runtime.lease import format_session_holder

    daemon = load_daemon(tmp_path, monkeypatch)
    proc = psutil.Process()
    live = format_session_holder("WIN-LEASE", proc.pid, proc.create_time(), "still-here")
    daemon.get_authority_store().acquire("worker:WIN-LEASE", live, "other-work", ttl_s=3600)
    with pytest.raises(RuntimeError, match="canonical writer lease"):
        daemon.acquire_lock("WIN-LEASE")
    assert daemon._lock_fd is None


def test_acquire_lock_holds_a_canonical_lease(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    lock_path = daemon.acquire_lock("WIN-LEASE")
    try:
        assert lock_path is not None
        assert daemon._worker_lease is not None
        assert daemon._worker_lease.workkey == "daemon_loop"
    finally:
        daemon.release_lock(lock_path)
    assert daemon._worker_lease is None
    assert daemon._lock_fd is None


def test_held_lock_means_another_instance(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    fake = types.ModuleType("msvcrt")
    fake.LK_NBLCK = 1

    def locking(_fd, _mode, _length):
        raise OSError("locked")

    fake.locking = locking
    monkeypatch.setitem(sys.modules, "msvcrt", fake)
    assert daemon.acquire_lock("WIN-01") is None
