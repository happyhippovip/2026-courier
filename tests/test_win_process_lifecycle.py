import os
import time
import subprocess
import pytest
import psutil
from courier_worker.host import _spawn_contained, ContainedRun, _terminate_job, _job_for_child, _assign_to_job

@pytest.mark.skipif(os.name != 'nt', reason='Windows specific')
def test_grandchild_process_reaping(tmp_path):
    run_dir = str(tmp_path)
    
    # Run a powershell that spawns a cmd and keeps both alive
    argv = [
        "powershell", "-Command",
        "Start-Process cmd; Start-Sleep -Seconds 30"
    ]
    
    run = _spawn_contained(argv, run_dir, "test-leak")
    
    # Verify the parent and grandchild are running
    try:
        parent_proc = psutil.Process(run.proc.pid)
    except psutil.NoSuchProcess:
        pytest.fail(f"Parent process exited immediately. Return code: {run.proc.poll()}")
        
    start_time = time.monotonic()
    children = []
    while time.monotonic() - start_time < 30:
        try:
            children = parent_proc.children(recursive=True)
            if len(children) > 0:
                break
        except psutil.NoSuchProcess:
            pytest.fail(f"Parent process died before spawning grandchild. Return code: {run.proc.poll()}")
        time.sleep(0.5)
        
    if not children:
        pytest.fail(f"Grandchild was not spawned within 30s. Parent return code: {run.proc.poll()}")
    
    child_pids = [c.pid for c in children]
    
    run.terminate_tree()
    run.proc.wait()
    
    # Assert descendants after is 0 (PID reuse safety check using psutil)
    time.sleep(2.0) # Wait for OS to reap
    
    for pid in child_pids:
        try:
            p = psutil.Process(pid)
            assert not p.is_running() or p.name() not in ["cmd.exe", "powershell.exe"], "Grandchild survived!"
        except psutil.NoSuchProcess:
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

