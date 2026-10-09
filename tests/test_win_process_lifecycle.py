import os
import time
import subprocess
import pytest
import psutil
from courier_worker.host import _spawn_contained, ContainedRun, _terminate_job, _job_for_child, _assign_to_job

def _wait_for_descendant(pid, name, timeout=30.0):
    """Poll for a descendant called `name`. Windows PowerShell can need several
    seconds to start on a cold CI runner, so a fixed sleep races the spawn."""
    parent = psutil.Process(pid)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if any(c.name().lower() == name for c in parent.children(recursive=True)):
                return True
        except psutil.NoSuchProcess:
            return False
        time.sleep(0.2)
    return False


@pytest.mark.skipif(os.name != 'nt', reason='Windows specific')
def test_grandchild_process_reaping(tmp_path):
    run_dir = str(tmp_path)

    # Run a powershell that spawns a hidden cmd and keeps both alive
    argv = [
        "powershell", "-NoProfile", "-Command",
        "Start-Process cmd -WindowStyle Hidden; Start-Sleep -Seconds 60"
    ]

    run = _spawn_contained(argv, run_dir, "test-leak")
    try:
        assert _wait_for_descendant(run.proc.pid, "cmd.exe"), "Grandchild was not spawned within 30 s"
        tree = [(c.pid, c.create_time()) for c in psutil.Process(run.proc.pid).children(recursive=True)
                if c.name().lower() in ("cmd.exe", "powershell.exe")]
    finally:
        run.terminate_tree()
        run.proc.wait()

    time.sleep(0.5)  # Wait for OS to reap

    # A live process with the same pid and creation time is a survivor; a reused pid is not
    for pid, created in tree:
        try:
            assert psutil.Process(pid).create_time() != created, f"Grandchild {pid} survived!"
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

@pytest.mark.skipif(os.name != 'nt', reason='Windows specific')
def test_repeated_spawn_cleanup(tmp_path):
    run_dir = str(tmp_path)
    
    for i in range(3):
        argv = [
            "powershell", "-Command",
            "Start-Sleep -Seconds 1"
        ]
        
        run = _spawn_contained(argv, run_dir, f"test-repeat-{i}")
        time.sleep(0.5)
        run.terminate_tree()
        assert run.proc.poll() is not None
        assert run.job is None

