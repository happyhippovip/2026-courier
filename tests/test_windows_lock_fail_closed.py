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
    dead = format_session_holder(daemon._session_device("WIN-LEASE"), 2**30, 1.0, "dead-session")
    store.acquire("worker:WIN-LEASE", dead, "daemon_loop", ttl_s=3600)
    lock_path = daemon.acquire_lock("WIN-LEASE")
    try:
        assert daemon._worker_lease is not None
        assert daemon._worker_lease.holder != dead
    finally:
        daemon.release_lock(lock_path)


def test_lease_lost_during_the_loop_does_not_claim(tmp_path, monkeypatch):
    """A fencing token that moves after startup is not a reason to take new work."""
    from dataclasses import replace

    from tests.test_windows_worker_contract import StopLoop

    daemon = load_daemon(tmp_path, monkeypatch)
    calls = []

    def urlopen(req, data=None, timeout=None):
        calls.append(req.full_url)
        return object()

    sleeps = {"n": 0}

    def sleep(_seconds):
        sleeps["n"] += 1
        if sleeps["n"] == 1:
            daemon._worker_lease = replace(daemon._worker_lease, token=daemon._worker_lease.token + 3)
            return
        raise StopLoop()

    monkeypatch.setattr(daemon, "read_cpu_load_percent", lambda: None)
    monkeypatch.setattr(daemon.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(daemon.time, "sleep", sleep)
    with pytest.raises(daemon.CanonicalLeaseLost):
        daemon.loop()
    assert sleeps["n"] == 1
    assert not any(url.endswith("/tasks/claim") for url in calls)


def test_foreign_host_dead_pid_is_not_a_local_restart(tmp_path, monkeypatch):
    """A pid that does not exist here does not make another host's lease free."""
    from courier_runtime.lease import format_session_holder

    daemon = load_daemon(tmp_path, monkeypatch)
    remote = format_session_holder("OTHER-HOST@remote", 2**30, 1.0, "remote-session")
    daemon.get_authority_store().acquire("worker:WIN-LEASE", remote, "daemon_loop", ttl_s=3600)
    with pytest.raises(daemon.CanonicalLeaseLost, match="canonical writer lease"):
        daemon.acquire_lock("WIN-LEASE")
    assert daemon._lock_fd is None
    assert daemon._worker_lease is None
    current = daemon.get_authority_store().current("worker:WIN-LEASE")
    assert current is not None and current.holder == remote


def test_live_holder_blocks_a_second_start(tmp_path, monkeypatch):
    import psutil
    from courier_runtime.lease import format_session_holder

    daemon = load_daemon(tmp_path, monkeypatch)
    proc = psutil.Process()
    live = format_session_holder(daemon._session_device("WIN-LEASE"), proc.pid, proc.create_time(), "still-here")
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


def test_lease_store_permission_error_does_not_start(tmp_path, monkeypatch):
    """CUR-WIN-036: a store that refuses writes is not a running worker."""
    daemon = load_daemon(tmp_path, monkeypatch)

    def denied():
        raise PermissionError("access denied")

    monkeypatch.setattr(daemon, "get_authority_store", denied)
    with pytest.raises(daemon.CanonicalLeaseLost, match="canonical writer lease"):
        daemon.acquire_lock("WIN-LEASE")
    assert daemon._lock_fd is None
    assert daemon._worker_lease is None


def test_none_lease_store_is_not_a_successful_lock(tmp_path, monkeypatch):
    """A missing LeaseStore connection is not a held lock and not a clean start."""
    daemon = load_daemon(tmp_path, monkeypatch)
    monkeypatch.setattr(daemon.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(daemon, "get_authority_store", lambda: None)
    fake = types.ModuleType("msvcrt")
    fake.LK_NBLCK = 1
    fake.LK_UNLCK = 2
    fake.locking = lambda _fd, _mode, _length: None
    monkeypatch.setitem(sys.modules, "msvcrt", fake)
    with pytest.raises(daemon.CanonicalLeaseLost, match="canonical writer lease"):
        daemon.acquire_lock("WIN-NONE")
    assert daemon._lock_fd is None
    assert daemon._worker_lease is None


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
    if os.name == "nt" or not hasattr(os, "geteuid"):
        pytest.skip("POSIX directory mode is not the Windows write check")
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


def test_lock_worker_id_rejects_a_windows_separator(tmp_path, monkeypatch):
    """A backslash is a path separator on Windows and must not name a lock."""
    daemon = load_daemon(tmp_path, monkeypatch)
    monkeypatch.setattr(daemon.tempfile, "gettempdir", lambda: str(tmp_path))
    with pytest.raises(ValueError, match="worker"):
        daemon.acquire_lock("WIN-01\\..\\outside")


def test_held_lock_means_another_instance(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    fake = types.ModuleType("msvcrt")
    fake.LK_NBLCK = 1

    def locking(_fd, _mode, _length):
        raise OSError("locked")

    fake.locking = locking
    monkeypatch.setitem(sys.modules, "msvcrt", fake)
    assert daemon.acquire_lock("WIN-01") is None


def _busy_msvcrt(monkeypatch):
    fake = types.ModuleType("msvcrt")
    fake.LK_NBLCK = 1

    def locking(_fd, _mode, _length):
        raise OSError("locked")

    fake.locking = locking
    monkeypatch.setitem(sys.modules, "msvcrt", fake)


def test_file_lock_without_canonical_lease_exits_3(tmp_path, monkeypatch):
    """CUR-WIN-039/044: the local file lock is not a running worker."""
    daemon = load_daemon(tmp_path, monkeypatch)
    (daemon.STATE_DIR / "authority.db").write_bytes(b"not a sqlite database")
    assert daemon.main() == 3
    assert daemon._lock_fd is None
    assert daemon._worker_lease is None
    lock_file = daemon.Path(daemon.tempfile.gettempdir()) / "courier_worker_WIN-01.lock"
    assert not lock_file.exists()


def test_missing_server_does_not_use_a_lan_default(tmp_path, monkeypatch):
    """CUR-WIN-084: no configured server must not fall back to a private LAN."""
    monkeypatch.delenv("COURIER_SERVER", raising=False)
    monkeypatch.delenv("COURIER_SERVER_URL", raising=False)
    daemon = load_daemon(tmp_path, monkeypatch)
    source = daemon.Path(daemon.__file__).read_text(encoding="utf-8")
    assert "192.168.178.162" not in source
    cfg = {"WORKER_ID": "WIN-01", "COURIER_API_KEY": "dummy-test-key-not-real"}
    (daemon.APP_DATA_DIR / "config.json").write_text(__import__("json").dumps(cfg))
    daemon.API_URL = ""
    calls = []
    monkeypatch.setattr(daemon.urllib.request, "urlopen", lambda *a, **k: calls.append(a))
    assert daemon.main() == 4
    assert calls == []


def test_configured_server_is_used(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_SERVER", "http://courier.invalid")
    daemon = load_daemon(tmp_path, monkeypatch)
    assert daemon.API_URL == "http://courier.invalid"


def test_missing_credential_exits_2(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    cfg = {"COURIER_SERVER": "http://courier.invalid", "WORKER_ID": "WIN-01", "COURIER_API_KEY": ""}
    (daemon.APP_DATA_DIR / "config.json").write_text(__import__("json").dumps(cfg))
    daemon.API_KEY = ""
    monkeypatch.setenv("COURIER_API_KEY", "")
    assert daemon.main() == 2


def test_unexpected_start_error_exits_1(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)

    def boom():
        raise RuntimeError("config unreadable")

    monkeypatch.setattr(daemon, "load_config", boom)
    assert daemon.main() == 1


def test_held_file_lock_exits_0_without_starting_work(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    _busy_msvcrt(monkeypatch)
    assert daemon.main() == 0
    assert daemon._worker_lease is None
