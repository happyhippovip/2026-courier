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


def test_missing_authority_store_does_not_keep_the_file_lock(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    original = daemon.get_authority_store
    monkeypatch.setattr(daemon, "get_authority_store", lambda: None)
    with pytest.raises(RuntimeError, match="refusing to run without a writer lease"):
        daemon.acquire_lock("WIN-01")
    assert daemon._lock_fd is None
    assert daemon._worker_lease is None

    monkeypatch.setattr(daemon, "get_authority_store", original)
    lock_path = daemon.acquire_lock("WIN-01")
    assert lock_path is not None
    assert daemon._worker_lease is not None
    daemon.release_lock(lock_path)
    assert daemon._lock_fd is None


def test_authority_lease_error_is_not_another_instance(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)

    class BrokenStore:
        def acquire(self, *_args, **_kwargs):
            raise RuntimeError("authority.db unreadable")

    monkeypatch.setattr(daemon, "get_authority_store", lambda: BrokenStore())
    with pytest.raises(RuntimeError, match="authority.db unreadable"):
        daemon.acquire_lock("WIN-01")
    assert daemon._lock_fd is None
    assert daemon._worker_lease is None


def test_authority_lease_conflict_defers(tmp_path, monkeypatch):
    from courier_runtime.lease import LeaseConflict

    daemon = load_daemon(tmp_path, monkeypatch)

    class HeldStore:
        def acquire(self, *_args, **_kwargs):
            raise LeaseConflict("worker scope is held")

    monkeypatch.setattr(daemon, "get_authority_store", lambda: HeldStore())
    assert daemon.acquire_lock("WIN-01") is None
    assert daemon._lock_fd is None
    assert daemon._worker_lease is None


def test_held_lock_means_another_instance(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    fake = types.ModuleType("msvcrt")
    fake.LK_NBLCK = 1

    def locking(_fd, _mode, _length):
        raise OSError("locked")

    fake.locking = locking
    monkeypatch.setitem(sys.modules, "msvcrt", fake)
    assert daemon.acquire_lock("WIN-01") is None
