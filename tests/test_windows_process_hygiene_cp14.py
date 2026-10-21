"""
tests/test_windows_process_hygiene_cp14.py — Contract tests for CP-14 / CQ-14
Windows Process Tree Termination, Identity Verification, and Hygiene

Invariants:
1. Exact Process Ownership required before stop/cleanup.
2. Verified identity check: PID + Process Create Time + Executable match before termination.
3. If PID was recycled by the OS (create_time mismatch, different executable), termination is ABORTED.
4. Scoped Process Tree Termination: terminates only owned child processes without touching parent shells,
   other agent windows, user-opened terminals, or unrelated applications.
5. Single-instance launch hygiene: ensures only one worker daemon instance, zero infinite batch wrappers,
   and zero process churn.
6. Diagnostic status checks are one-shot, structured, and strictly bounded (no polling loops).
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
import pytest

from courier_core.windows_process_hygiene import (
    ProcessOwnershipRecord,
    create_current_ownership_record,
    get_bounded_worker_status,
    load_ownership_record,
    safe_terminate_owned_process_tree,
    save_ownership_record,
    verify_process_identity,
)


def test_ownership_record_serialization_and_integrity(tmp_path):
    """Invariant 1: Durable ownership record captures all required identity fields."""
    record_file = tmp_path / "worker_ownership.json"
    rec = ProcessOwnershipRecord(
        service_id="courier-worker-test",
        worker_id="WIN-HYGIENE-01",
        pid=12345,
        process_create_time=1700000000.0,
        executable=r"C:\Python\python.exe",
        daemon_path=r"C:\courier\daemon.py",
        started_at=1700000001.0,
        cmdline=["python", "daemon.py"],
    )

    save_ownership_record(rec, record_file)
    assert record_file.is_file()

    loaded = load_ownership_record(record_file)
    assert loaded is not None
    assert loaded.service_id == "courier-worker-test"
    assert loaded.worker_id == "WIN-HYGIENE-01"
    assert loaded.pid == 12345
    assert loaded.process_create_time == 1700000000.0
    assert loaded.executable == r"C:\Python\python.exe"
    assert loaded.daemon_path == r"C:\courier\daemon.py"
    assert loaded.started_at == 1700000001.0
    assert loaded.cmdline == ["python", "daemon.py"]


def test_verify_process_identity_matches_live_process():
    """Invariant 2: Identity check succeeds for the genuine running process."""
    current_rec = create_current_ownership_record(worker_id="WIN-SELF-01")
    assert current_rec.pid == os.getpid()
    assert verify_process_identity(current_rec) is True


def test_recycled_pid_fails_verification_and_aborts_kill(tmp_path):
    """Invariant 3: If PID was recycled by the OS, verification fails and kill is ABORTED."""
    # Use current PID so the PID physically exists, but corrupt create_time to simulate recycled PID
    corrupted_rec = ProcessOwnershipRecord(
        service_id="courier-worker",
        worker_id="WIN-RECYCLED-01",
        pid=os.getpid(),
        process_create_time=100.0,  # 100 seconds after epoch -> cannot match current process
        executable=sys.executable,
        daemon_path="fake_daemon.py",
        started_at=time.time(),
    )

    record_file = tmp_path / "recycled_ownership.json"
    save_ownership_record(corrupted_rec, record_file)

    # 1. Verification must fail
    assert verify_process_identity(corrupted_rec) is False

    # 2. Safe terminate must abort kill and return False
    killed = safe_terminate_owned_process_tree(corrupted_rec, timeout_s=1.0, ownership_file=record_file)
    assert killed is False

    # 3. We are still alive! (Current process was NOT terminated)
    assert os.getpid() == corrupted_rec.pid


def test_safe_terminate_reaps_only_owned_process_and_its_descendants(tmp_path):
    """Invariant 4: Safe terminate reaps exact child process tree without collateral damage."""
    # Spawn a real child that in turn spawns a grandchild
    script = (
        "import subprocess, sys, time\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "time.sleep(60)\n"
    )
    child = subprocess.Popen([sys.executable, "-c", script])
    time.sleep(0.5)

    rec = create_current_ownership_record(worker_id="WIN-SPAWNED-01", pid=child.pid)
    record_file = tmp_path / "spawned_ownership.json"
    save_ownership_record(rec, record_file)

    assert verify_process_identity(rec) is True

    # Terminate the owned tree
    stopped = safe_terminate_owned_process_tree(rec, timeout_s=5.0, ownership_file=record_file)
    assert stopped is True

    # Child must be terminated
    child.poll()
    assert child.returncode is not None
    assert not record_file.exists()


def test_bounded_worker_status_exits_promptly_without_polling(tmp_path):
    """Invariant 6: Status check is bounded, one-shot, and returns structured state."""
    record_file = tmp_path / "status_test.json"

    # 1. Non-existent file
    status = get_bounded_worker_status(record_file)
    assert status["status"] == "STOPPED"
    assert status["running"] is False

    # 2. Live process
    rec = create_current_ownership_record(worker_id="WIN-STATUS-01")
    save_ownership_record(rec, record_file)
    status = get_bounded_worker_status(record_file)
    assert status["status"] == "RUNNING"
    assert status["running"] is True
    assert status["worker_id"] == "WIN-STATUS-01"
    assert status["pid"] == os.getpid()

    # 3. Dead/recycled process
    stale_rec = ProcessOwnershipRecord(
        service_id="courier-worker",
        worker_id="WIN-STATUS-01",
        pid=999999,  # Unlikely to exist
        process_create_time=1.0,
        executable="python.exe",
        daemon_path="daemon.py",
        started_at=1.0,
    )
    save_ownership_record(stale_rec, record_file)
    status = get_bounded_worker_status(record_file)
    assert status["status"] == "STALE_OR_RECYCLED"
    assert status["running"] is False


def test_cli_process_ownership_status_and_stop(tmp_path):
    """Contract: process_ownership.py CLI executes prompt one-shot commands."""
    record_file = tmp_path / "cli_ownership.json"
    cli_path = Path(__file__).resolve().parents[1] / "scripts" / "windows_worker" / "process_ownership.py"

    # 1. Status on empty
    res = subprocess.run([sys.executable, str(cli_path), "status", "--ownership-file", str(record_file)],
                         capture_output=True, text=True)
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["status"] == "STOPPED"

    # 2. Record current process
    res = subprocess.run([sys.executable, str(cli_path), "record", "--ownership-file", str(record_file),
                          "--worker-id", "CLI-TEST-01", "--pid", str(os.getpid())],
                         capture_output=True, text=True)
    assert res.returncode == 0
    assert record_file.is_file()

    # 3. Status on live process
    res = subprocess.run([sys.executable, str(cli_path), "status", "--ownership-file", str(record_file)],
                         capture_output=True, text=True)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["status"] == "RUNNING"
    assert data["worker_id"] == "CLI-TEST-01"
