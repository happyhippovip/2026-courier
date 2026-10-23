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


def test_lock_symlink_is_not_truncated(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    monkeypatch.setattr(daemon.tempfile, "gettempdir", lambda: str(tmp_path))
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")
    lock = tmp_path / "courier_worker_WIN-01.lock"
    lock.symlink_to(outside)
    try:
        daemon.acquire_lock("WIN-01")
    except OSError as exc:
        assert "symlink" in str(exc)
    assert outside.read_text(encoding="utf-8") == "keep"


def test_lock_worker_id_cannot_escape_the_temp_dir(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    temp = tmp_path / "temp"
    temp.mkdir()
    monkeypatch.setattr(daemon.tempfile, "gettempdir", lambda: str(temp))
    (temp / "courier_worker_..").mkdir()
    worker_id = "../../../escaped"
    victim = tmp_path / "escaped.lock"
    victim.write_text("keep", encoding="utf-8")
    try:
        daemon.acquire_lock(worker_id)
    except (OSError, ValueError) as exc:
        assert "worker" in str(exc).lower()
    assert victim.read_text(encoding="utf-8") == "keep"


def test_windows_lock_does_not_cover_the_pid_record(tmp_path, monkeypatch):
    """The mandatory Windows lock sits past the pid bytes, then releases there."""
    daemon = load_daemon(tmp_path, monkeypatch)
    monkeypatch.setattr(daemon.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(daemon, "get_authority_store", lambda: None)
    seen = []
    fake = types.ModuleType("msvcrt")
    fake.LK_NBLCK = 1
    fake.LK_UNLCK = 2

    def locking(fd, mode, length):
        seen.append((os.lseek(fd, 0, os.SEEK_CUR), mode, length))

    fake.locking = locking
    monkeypatch.setitem(sys.modules, "msvcrt", fake)
    path = daemon.acquire_lock("WIN-01")
    assert path is not None
    assert seen[0] == (daemon._WIN_LOCK_OFFSET, fake.LK_NBLCK, 1)
    record = path.read_bytes()
    assert record.startswith(b"{")
    assert b'"pid"' in record
    daemon.release_lock(path)
    assert seen[1] == (daemon._WIN_LOCK_OFFSET, fake.LK_UNLCK, 1)


def test_held_lock_means_another_instance(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    fake = types.ModuleType("msvcrt")
    fake.LK_NBLCK = 1

    def locking(_fd, _mode, _length):
        raise OSError("locked")

    fake.locking = locking
    monkeypatch.setitem(sys.modules, "msvcrt", fake)
    assert daemon.acquire_lock("WIN-01") is None
