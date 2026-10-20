import json
import time
import pytest
from pathlib import Path
from courier_core.lock_manager import (
    DistributedLockManager,
    LockHandle,
    StaleFencingTokenError,
    LockState,
)


def test_acquire_and_release_happy_path(tmp_path):
    storage_dir = tmp_path / "locks"
    manager = DistributedLockManager(storage_dir=storage_dir)

    handle = manager.acquire(resource_id="ledger-writer", holder="worker-1", ttl_seconds=10.0)
    assert handle is not None
    assert handle.resource_id == "ledger-writer"
    assert handle.holder == "worker-1"
    assert handle.fencing_token == 1
    assert handle.is_active()

    # Release
    released = manager.release(handle)
    assert released is True

    # After release, handle is no longer active
    assert not handle.is_active()


def test_competing_holders_mutual_exclusion(tmp_path):
    storage_dir = tmp_path / "locks"
    manager1 = DistributedLockManager(storage_dir=storage_dir)
    manager2 = DistributedLockManager(storage_dir=storage_dir)

    # Worker 1 acquires
    h1 = manager1.acquire(resource_id="shared-resource", holder="worker-1", ttl_seconds=10.0)
    assert h1 is not None

    # Worker 2 attempts to acquire same resource while active
    h2 = manager2.acquire(resource_id="shared-resource", holder="worker-2", ttl_seconds=10.0)
    assert h2 is None

    # Clean release by worker 1
    manager1.release(h1)

    # Now worker 2 can acquire
    h2_after = manager2.acquire(resource_id="shared-resource", holder="worker-2", ttl_seconds=10.0)
    assert h2_after is not None
    assert h2_after.fencing_token == 2
    manager2.release(h2_after)


def test_expired_lock_stealing_increments_fencing_token(tmp_path):
    storage_dir = tmp_path / "locks"
    manager = DistributedLockManager(storage_dir=storage_dir)

    # Worker 1 acquires with very short TTL
    h1 = manager.acquire(resource_id="fast-expire", holder="worker-1", ttl_seconds=0.1)
    assert h1 is not None
    assert h1.fencing_token == 1

    time.sleep(0.2)  # Wait for expiry

    # Worker 2 acquires after expiry
    h2 = manager.acquire(resource_id="fast-expire", holder="worker-2", ttl_seconds=10.0)
    assert h2 is not None
    assert h2.holder == "worker-2"
    assert h2.fencing_token == 2  # Monotonically higher
    assert h2.fencing_token > h1.fencing_token

    manager.release(h2)


def test_split_brain_protection_stale_token_rejected(tmp_path):
    storage_dir = tmp_path / "locks"
    manager = DistributedLockManager(storage_dir=storage_dir)

    # Worker 1 gets token 1
    h1 = manager.acquire(resource_id="data-sink", holder="worker-1", ttl_seconds=0.1)
    assert h1 is not None
    assert h1.fencing_token == 1

    time.sleep(0.2)  # Expire

    # Worker 2 steals lock and gets token 2
    h2 = manager.acquire(resource_id="data-sink", holder="worker-2", ttl_seconds=10.0)
    assert h2 is not None
    assert h2.fencing_token == 2

    # Worker 2 writes safely
    write_executed = []
    res2 = manager.guard_write(
        resource_id="data-sink",
        fencing_token=h2.fencing_token,
        write_action=lambda: write_executed.append("worker-2-write")
    )
    assert "worker-2-write" in write_executed

    # Worker 1 wakes up with stale token 1 and attempts guarded write
    with pytest.raises(StaleFencingTokenError) as exc_info:
        manager.guard_write(
            resource_id="data-sink",
            fencing_token=h1.fencing_token,
            write_action=lambda: write_executed.append("worker-1-stale-write")
        )
    assert "Stale fencing token" in str(exc_info.value)
    assert "worker-1-stale-write" not in write_executed


def test_lock_renewal(tmp_path):
    storage_dir = tmp_path / "locks"
    manager = DistributedLockManager(storage_dir=storage_dir)

    h = manager.acquire(resource_id="long-job", holder="worker-1", ttl_seconds=2.0)
    assert h is not None
    initial_token = h.fencing_token
    initial_expiry = h.expires_at

    time.sleep(0.1)
    renewed = manager.renew(h, ttl_seconds=5.0)
    assert renewed is True
    assert h.fencing_token == initial_token
    assert h.expires_at > initial_expiry

    manager.release(h)


def test_unauthorized_or_corrupt_release(tmp_path):
    storage_dir = tmp_path / "locks"
    manager = DistributedLockManager(storage_dir=storage_dir)

    h1 = manager.acquire(resource_id="protected-res", holder="worker-1", ttl_seconds=10.0)
    assert h1 is not None

    # Rogue handle from another worker
    fake_handle = LockHandle(
        resource_id="protected-res",
        holder="rogue-worker",
        fencing_token=h1.fencing_token,
        expires_at=h1.expires_at,
        _manager=manager,
    )

    # Rogue release rejected
    assert manager.release(fake_handle) is False

    # Legitimate release accepted
    assert manager.release(h1) is True


def test_cli_invocation(tmp_path):
    import subprocess
    import sys

    storage_dir = tmp_path / "cli_locks"

    # Acquire lock via CLI
    cmd_acq = [
        sys.executable,
        "-m",
        "courier_core.lock_manager",
        "acquire",
        "--storage",
        str(storage_dir),
        "--resource",
        "cli-res",
        "--holder",
        "cli-worker",
        "--ttl",
        "5.0",
    ]
    proc_acq = subprocess.run(cmd_acq, capture_output=True, text=True, check=True)
    out_acq = json.loads(proc_acq.stdout)
    assert out_acq["status"] == "ACQUIRED"
    assert out_acq["fencing_token"] == 1

    # Validate lock via CLI
    cmd_val = [
        sys.executable,
        "-m",
        "courier_core.lock_manager",
        "validate",
        "--storage",
        str(storage_dir),
        "--resource",
        "cli-res",
        "--token",
        "1",
    ]
    proc_val = subprocess.run(cmd_val, capture_output=True, text=True, check=True)
    out_val = json.loads(proc_val.stdout)
    assert out_val["valid"] is True

    # Release via CLI
    cmd_rel = [
        sys.executable,
        "-m",
        "courier_core.lock_manager",
        "release",
        "--storage",
        str(storage_dir),
        "--resource",
        "cli-res",
        "--holder",
        "cli-worker",
        "--token",
        "1",
    ]
    proc_rel = subprocess.run(cmd_rel, capture_output=True, text=True, check=True)
    out_rel = json.loads(proc_rel.stdout)
    assert out_rel["released"] is True


def test_resource_id_collision_and_expired_renew_rejected(tmp_path):
    storage_dir = tmp_path / "collision_locks"
    manager = DistributedLockManager(storage_dir=storage_dir)

    # "lane/a" and "lane_a" must not collide on disk
    h_slash = manager.acquire(resource_id="lane/a", holder="worker-1", ttl_seconds=10.0)
    h_under = manager.acquire(resource_id="lane_a", holder="worker-2", ttl_seconds=10.0)
    assert h_slash is not None
    assert h_under is not None
    assert h_slash.is_active() is True
    assert h_under.is_active() is True

    # Expired lock cannot be renewed even before another worker steals it
    h_exp = manager.acquire(resource_id="short-lived", holder="worker-1", ttl_seconds=0.05)
    assert h_exp is not None
    time.sleep(0.1)
    assert manager.renew(h_exp, ttl_seconds=10.0) is False


def test_sweeper_preserves_user_temp_and_explorer_browsers(tmp_path, monkeypatch):
    import psutil
    from courier_worker.sweeper import cleanup_temp_if_large, terminate_orphaned_drivers

    user_file = tmp_path / "important_user_doc.txt"
    user_file.write_bytes(b"x" * 2048)
    owned_dir = tmp_path / "scoped_dir12345"
    owned_dir.mkdir()
    (owned_dir / "driver.log").write_bytes(b"y" * 2048)

    removed = cleanup_temp_if_large(max_size_gb=0.0, temp_dir=str(tmp_path))
    assert removed == 1
    assert user_file.exists() is True
    assert owned_dir.exists() is False

    # Fake process list: chrome.exe parented by explorer.exe must NEVER be terminated;
    # chromedriver.exe with dead parent (NoSuchProcess) IS terminated.
    terminated_pids = []

    class FakeProc:
        def __init__(self, pid, name, ppid):
            self.info = {"pid": pid, "name": name, "ppid": ppid}

        def terminate(self):
            terminated_pids.append(self.info["pid"])

        def wait(self, timeout=None):
            return 0

    def fake_process_iter(attrs):
        return [
            FakeProc(101, "chrome.exe", 500),
            FakeProc(102, "msedge.exe", 500),
            FakeProc(103, "chromedriver.exe", 500),
            FakeProc(104, "chromedriver.exe", 999999),
        ]

    class FakeParent:
        def __init__(self, pid):
            if pid == 999999:
                raise psutil.NoSuchProcess(pid)
            self.pid = pid

        def name(self):
            return "explorer.exe"

        def is_running(self):
            return True

    monkeypatch.setattr(psutil, "process_iter", fake_process_iter)
    monkeypatch.setattr(psutil, "Process", FakeParent)

    count = terminate_orphaned_drivers()
    assert count == 1
    assert terminated_pids == [104]
