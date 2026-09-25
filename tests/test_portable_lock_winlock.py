"""Tests for platform-neutral locking (fcntl on POSIX/Mac, msvcrt on Windows).

Verifies Focus B.1:
1. All locking modules can be imported when fcntl is absent/unimportable (Windows).
2. POSIX path operates reliably with fcntl on Mac/Unix.
3. Windows path operates reliably using msvcrt simulation and mock verification.
"""
import importlib
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.cannon.mac_launcher as mac_launcher
import app.cannon.storage as cannon_storage
from app.cannon.storage import InstanceLock
import pre_courier_muse.muse_runner as muse_runner
import scripts.agent_handoff_ledger as agent_handoff_ledger
from scripts.agent_handoff_ledger import _lock_stream, _unlock_stream
import scripts.mac_adapter as mac_adapter
from scripts.mac_adapter import MacAdapter


def test_import_without_fcntl(monkeypatch):
    """Verify that locking modules import cleanly even if fcntl does not exist."""
    monkeypatch.setitem(sys.modules, "fcntl", None)

    # Force reimport of target modules to prove no top-level 'import fcntl' crashes
    modules_to_test = [
        "scripts.mac_adapter",
        "app.cannon.mac_launcher",
        "app.cannon.storage",
        "scripts.agent_handoff_ledger",
        "pre_courier_muse.muse_runner",
    ]
    for mod_name in modules_to_test:
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        mod = importlib.import_module(mod_name)
        assert mod is not None


@pytest.mark.skipif(os.name == "nt", reason="POSIX fcntl test")
def test_posix_instance_lock_mutual_exclusion(tmp_path, monkeypatch):
    """Verify InstanceLock on POSIX enforces single-instance mutual exclusion via fcntl."""
    monkeypatch.setattr(cannon_storage, "owned", lambda p: Path(p))

    lock_dir = tmp_path / "instance_state"
    with InstanceLock(lock_dir):
        # Concurrent acquisition must fail
        with pytest.raises(RuntimeError, match="CANNON_ALREADY_RUNNING"):
            with InstanceLock(lock_dir):
                pass

    # After exit, lock should be free
    with InstanceLock(lock_dir):
        pass


@pytest.mark.skipif(os.name == "nt", reason="POSIX fcntl test")
def test_posix_mac_adapter_supervise_lock(tmp_path):
    """Verify MacAdapter.supervise uses flock and rejects concurrent runs."""
    import fcntl

    adapter = MacAdapter(tmp_path)
    lock_file = tmp_path / "supervisor.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    with lock_file.open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = adapter.supervise(max_cycles=1)
        assert result == {"started": False, "reason": "supervisor_active"}


@pytest.mark.skipif(os.name == "nt", reason="POSIX fcntl test")
def test_posix_muse_runner_lock(tmp_path):
    """Verify muse_runner acquire_lock and release_lock on POSIX."""
    lock_path = tmp_path / "muse.lock"
    fd1 = muse_runner.acquire_lock(lock_path)
    assert fd1 is not None

    # Concurrent acquire must fail
    fd2 = muse_runner.acquire_lock(lock_path)
    assert fd2 is None

    muse_runner.release_lock(fd1)

    # After release, acquire succeeds
    fd3 = muse_runner.acquire_lock(lock_path)
    assert fd3 is not None
    muse_runner.release_lock(fd3)


def test_windows_simulation_instance_lock(tmp_path, monkeypatch):
    """Verify InstanceLock uses msvcrt.locking on Windows."""
    mock_os = MagicMock(wraps=os)
    mock_os.name = "nt"
    monkeypatch.setattr(cannon_storage, "os", mock_os)
    monkeypatch.setattr(cannon_storage, "owned", lambda p: Path(p))

    mock_msvcrt = MagicMock()
    mock_msvcrt.LK_NBLCK = 1
    mock_msvcrt.LK_UNLCK = 2
    monkeypatch.setitem(sys.modules, "msvcrt", mock_msvcrt)

    lock_dir = tmp_path / "instance_state_win"
    with InstanceLock(lock_dir):
        assert mock_msvcrt.locking.called
        # Check first call is lock (LK_NBLCK)
        first_call = mock_msvcrt.locking.call_args_list[0]
        assert first_call[0][1] == mock_msvcrt.LK_NBLCK
        assert first_call[0][2] == 1

    # Check last call is unlock (LK_UNLCK)
    last_call = mock_msvcrt.locking.call_args_list[-1]
    assert last_call[0][1] == mock_msvcrt.LK_UNLCK
    assert last_call[0][2] == 1


def test_windows_simulation_instance_lock_conflict(tmp_path, monkeypatch):
    """Verify InstanceLock raises CANNON_ALREADY_RUNNING on Windows lock collision."""
    mock_os = MagicMock(wraps=os)
    mock_os.name = "nt"
    monkeypatch.setattr(cannon_storage, "os", mock_os)
    monkeypatch.setattr(cannon_storage, "owned", lambda p: Path(p))

    mock_msvcrt = MagicMock()
    mock_msvcrt.LK_NBLCK = 1
    mock_msvcrt.locking.side_effect = OSError(13, "Permission denied")
    monkeypatch.setitem(sys.modules, "msvcrt", mock_msvcrt)

    lock_dir = tmp_path / "instance_state_win_conflict"
    with pytest.raises(RuntimeError, match="CANNON_ALREADY_RUNNING"):
        with InstanceLock(lock_dir):
            pass


def test_windows_simulation_mac_adapter_supervise(tmp_path, monkeypatch):
    """Verify MacAdapter.supervise uses msvcrt.locking on Windows."""
    mock_os = MagicMock(wraps=os)
    mock_os.name = "nt"
    monkeypatch.setattr(mac_adapter, "os", mock_os)

    mock_msvcrt = MagicMock()
    mock_msvcrt.LK_NBLCK = 1
    mock_msvcrt.LK_UNLCK = 2
    monkeypatch.setitem(sys.modules, "msvcrt", mock_msvcrt)

    adapter = MacAdapter(tmp_path)
    res = adapter.supervise(max_cycles=1, start=("begrenzt", 1, 0, True))
    assert res.get("snapshot", {}).get("invariants", {}).get("MAX_ACTIVE") == 1

    # Verify msvcrt.locking was called with LK_NBLCK on enter and LK_UNLCK on exit
    calls = mock_msvcrt.locking.call_args_list
    assert any(c[0][1] == mock_msvcrt.LK_NBLCK for c in calls)
    assert any(c[0][1] == mock_msvcrt.LK_UNLCK for c in calls)


def test_windows_simulation_mac_adapter_supervise_conflict(tmp_path, monkeypatch):
    """Verify MacAdapter.supervise handles collision gracefully on Windows."""
    mock_os = MagicMock(wraps=os)
    mock_os.name = "nt"
    monkeypatch.setattr(mac_adapter, "os", mock_os)

    mock_msvcrt = MagicMock()
    mock_msvcrt.LK_NBLCK = 1
    mock_msvcrt.locking.side_effect = OSError(13, "Permission denied")
    monkeypatch.setitem(sys.modules, "msvcrt", mock_msvcrt)

    adapter = MacAdapter(tmp_path)
    res = adapter.supervise(max_cycles=1)
    assert res == {"started": False, "reason": "supervisor_active"}


def test_windows_simulation_agent_handoff_stream_lock(tmp_path, monkeypatch):
    """Verify _lock_stream and _unlock_stream use msvcrt on Windows."""
    mock_os = MagicMock(wraps=os)
    mock_os.name = "nt"
    monkeypatch.setattr(agent_handoff_ledger, "os", mock_os)

    mock_msvcrt = MagicMock()
    mock_msvcrt.LK_NBLCK = 1
    mock_msvcrt.LK_UNLCK = 2
    monkeypatch.setitem(sys.modules, "msvcrt", mock_msvcrt)

    stream_file = tmp_path / "test.stream"
    with stream_file.open("a+b") as s:
        s.write(b"0")
        s.flush()
        _lock_stream(s)
        assert mock_msvcrt.locking.call_args[0][1] == mock_msvcrt.LK_NBLCK

        _unlock_stream(s)
        assert mock_msvcrt.locking.call_args[0][1] == mock_msvcrt.LK_UNLCK


def test_windows_simulation_mac_launcher_main(tmp_path, monkeypatch):
    """Verify mac_launcher.main uses msvcrt on Windows."""
    mock_os = MagicMock(wraps=os)
    mock_os.name = "nt"
    monkeypatch.setattr(mac_launcher, "os", mock_os)
    monkeypatch.setattr(mac_launcher.Path, "home", lambda: tmp_path)

    mock_msvcrt = MagicMock()
    mock_msvcrt.LK_NBLCK = 1
    mock_msvcrt.LK_UNLCK = 2
    monkeypatch.setitem(sys.modules, "msvcrt", mock_msvcrt)
    monkeypatch.setattr(mac_launcher, "open_cannon", lambda: 0)

    res = mac_launcher.main()
    assert res == 0
    calls = mock_msvcrt.locking.call_args_list
    assert any(c[0][1] == mock_msvcrt.LK_NBLCK for c in calls)
    assert any(c[0][1] == mock_msvcrt.LK_UNLCK for c in calls)


def test_windows_simulation_muse_runner_lock(tmp_path, monkeypatch):
    """Verify muse_runner acquire_lock and release_lock on Windows (sys.platform == 'win32')."""
    monkeypatch.setattr(muse_runner.sys, "platform", "win32")
    mock_msvcrt = MagicMock()
    mock_msvcrt.LK_NBLCK = 1
    mock_msvcrt.LK_UNLCK = 2
    monkeypatch.setitem(sys.modules, "msvcrt", mock_msvcrt)

    lock_path = tmp_path / "muse_win.lock"
    fd = muse_runner.acquire_lock(lock_path)
    assert fd is not None
    assert mock_msvcrt.locking.call_args[0][1] == mock_msvcrt.LK_NBLCK

    muse_runner.release_lock(fd)
    assert mock_msvcrt.locking.call_args[0][1] == mock_msvcrt.LK_UNLCK
