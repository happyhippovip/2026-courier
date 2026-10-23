"""A lock that cannot be created is a failed start, not a second instance."""
import os
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


def test_missing_lease_store_does_not_start(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)

    def missing():
        raise ImportError("courier_runtime.lease is not available")

    monkeypatch.setattr(daemon, "get_authority_store", missing)
    with pytest.raises(RuntimeError, match="canonical writer lease"):
        daemon.acquire_lock("WIN-LEASE")
    assert daemon._lock_fd is None
    assert daemon._worker_lease is None


def test_lease_store_without_write_permission_does_not_start(tmp_path, monkeypatch):
    if os.geteuid() == 0:
        pytest.skip("root ignores the directory mode used for this check")
    daemon = load_daemon(tmp_path, monkeypatch)
    database = daemon.STATE_DIR / "authority.db"
    if database.exists():
        database.unlink()
    daemon.STATE_DIR.chmod(0o555)
    try:
        with pytest.raises(RuntimeError, match="canonical writer lease"):
            daemon.acquire_lock("WIN-LEASE")
    finally:
        daemon.STATE_DIR.chmod(0o755)
    assert daemon._lock_fd is None
    assert daemon._worker_lease is None


def test_expired_canonical_lease_is_replaced(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    store = daemon.get_authority_store()
    store.db.execute(
        "INSERT INTO lease(scope, holder, workkey, token, expires_at) VALUES(?,?,?,?,?)",
        ("worker:WIN-LEASE", "old-host:1:1.0000:expired", "daemon_loop", 4, 1.0),
    )
    lock_path = daemon.acquire_lock("WIN-LEASE")
    try:
        assert daemon._worker_lease is not None
        assert daemon._worker_lease.token == 5
        assert daemon._worker_lease.holder != "old-host:1:1.0000:expired"
    finally:
        daemon.release_lock(lock_path)


def test_stale_fencing_token_blocks_work(tmp_path, monkeypatch):
    from dataclasses import replace

    daemon = load_daemon(tmp_path, monkeypatch)
    lock_path = daemon.acquire_lock("WIN-LEASE")
    original = daemon._worker_lease
    try:
        daemon._worker_lease = replace(original, token=original.token + 9)
        with pytest.raises(daemon.CanonicalLeaseLost, match="canonical writer lease"):
            daemon._require_canonical_lease()
    finally:
        daemon._worker_lease = original
        daemon.release_lock(lock_path)


def test_held_lock_means_another_instance(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    fake = types.ModuleType("msvcrt")
    fake.LK_NBLCK = 1

    def locking(_fd, _mode, _length):
        raise OSError("locked")

    fake.locking = locking
    monkeypatch.setitem(sys.modules, "msvcrt", fake)
    assert daemon.acquire_lock("WIN-01") is None
