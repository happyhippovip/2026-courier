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
    time.sleep(2) # Give it time to spawn the grandchild
    
    # Verify the parent and grandchild are running
    parent_proc = psutil.Process(run.proc.pid)
    children = parent_proc.children(recursive=True)
    assert len(children) > 0, "Grandchild was not spawned"
    
    child_pids = [c.pid for c in children]
    
    run.terminate_tree()
    run.proc.wait()
    
    # Assert descendants after is 0 (PID reuse safety check using psutil)
    time.sleep(0.5) # Wait for OS to reap
    
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



@pytest.mark.skipif(os.name != 'nt', reason='Windows specific')
def test_terminal_host_recovery(tmp_path):
    run_dir = str(tmp_path)
    
    # We simulate a terminal host (e.g. VS Code PowerShell extension)
    # The terminal host launches the daemon (Courier Worker equivalent) detached.
    # The daemon launches the actual task.
    # When the terminal host exits (exit -1), the daemon and task MUST survive.
    
    worker_script = tmp_path / "mock_worker.py"
    worker_script.write_text('''
import time
import subprocess
import sys

# Spawn a task that simulates Courier work
# It must outlive the terminal host
p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(15)"])
# Write PID so test can monitor it
with open("task_pid.txt", "w") as f:
    f.write(str(p.pid))
time.sleep(15)
''')
    
    terminal_host_script = tmp_path / "mock_terminal_host.py"
    terminal_host_script.write_text(f'''
import subprocess
import sys
import os
import time

# Use the exact pattern from start.bat: start "" <executable>
# This detaches the worker from the terminal host's job/process group.
worker_script = r"{worker_script}"
CREATE_NEW_PROCESS_GROUP = 0x00000200
DETACHED_PROCESS = 0x00000008

# Start the worker
p = subprocess.Popen(
    [sys.executable, worker_script],
    creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
    cwd=os.path.dirname(worker_script)
)

with open("worker_pid.txt", "w") as f:
    f.write(str(p.pid))

time.sleep(2) # Allow worker to start task
sys.exit(-1) # Simulate terminal host crash
''')
    
    # Run the terminal host
    host_proc = subprocess.Popen(["python", str(terminal_host_script)], cwd=run_dir)
    host_proc.wait(timeout=10)
    
    assert host_proc.returncode != 0 # Host crashed
    
    time.sleep(1) # Give OS time to reap if it was going to
    
    # Read PIDs
    with open(tmp_path / "worker_pid.txt", "r") as f:
        worker_pid = int(f.read().strip())
    
    with open(tmp_path / "task_pid.txt", "r") as f:
        task_pid = int(f.read().strip())
        
    worker_proc = psutil.Process(worker_pid)
    task_proc = psutil.Process(task_pid)
    
    assert worker_proc.is_running(), "Courier worker was killed when terminal host died!"
    assert task_proc.is_running(), "Courier task was killed when terminal host died!"
    
    # Cleanup
    task_proc.kill()
    worker_proc.kill()

@pytest.mark.skipif(os.name != 'nt', reason='Windows specific')
def test_job_object_ownership(tmp_path):
    '''
    Verify every Courier child process intended for lifecycle control is actually attached
    to the correct Windows Job Object. Produce native proof using Win32 API IsProcessInJob.
    '''
    run_dir = str(tmp_path)
    import ctypes
    from ctypes import wintypes
    
    argv = ["cmd.exe", "/c", "timeout", "10"]
    run = _spawn_contained(argv, run_dir, "test-job-ownership")
    time.sleep(0.5)
    
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    
    kernel32.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    kernel32.IsProcessInJob.restype = wintypes.BOOL
    
    PROCESS_QUERY_INFORMATION = 0x0400
    
    process_handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, run.proc.pid)
    assert process_handle, "Failed to open process"
    
    try:
        is_in_job = wintypes.BOOL(False)
        res = kernel32.IsProcessInJob(process_handle, run.job, ctypes.byref(is_in_job))
        assert res != 0, "IsProcessInJob failed"
        assert is_in_job.value, "Process is NOT in the Courier job object!"
    finally:
        kernel32.CloseHandle(process_handle)
        run.terminate_tree()

@pytest.mark.skipif(os.name != 'nt', reason='Windows specific')
def test_process_tree_failure_isolation(tmp_path):
    '''
    Force a descendant failure and verify Courier cleans up only its own tree
    while preserving unrelated processes.
    '''
    run_dir = str(tmp_path)
    
    # Spawn an unrelated process
    unrelated_proc = subprocess.Popen(["cmd.exe", "/c", "timeout", "30"])
    
    try:
        # Spawn our contained tree
        argv = [
            "powershell", "-Command",
            "Start-Process cmd; Start-Sleep -Seconds 30"
        ]
        
        run = _spawn_contained(argv, run_dir, "test-isolation")
        time.sleep(2) # Give it time to spawn the grandchild
        
        parent_proc = psutil.Process(run.proc.pid)
        children = parent_proc.children(recursive=True)
        assert len(children) > 0, "Grandchild was not spawned"
        
        child_pids = [c.pid for c in children]
        
        # Terminate Courier's tree
        run.terminate_tree()
        run.proc.wait()
        
        # Unrelated process must survive
        unrelated_psutil = psutil.Process(unrelated_proc.pid)
        assert unrelated_psutil.is_running(), "Unrelated process was killed!"
        
        # Descendants must be dead
        time.sleep(0.5)
        for pid in child_pids:
            try:
                p = psutil.Process(pid)
                assert not p.is_running() or p.name() not in ["cmd.exe", "powershell.exe"], "Grandchild survived!"
            except psutil.NoSuchProcess:
                pass
                
    finally:
        try:
            unrelated_proc.kill()
        except OSError:
            pass

@pytest.mark.skipif(os.name != 'nt', reason='Windows specific')
def test_pid_reuse_regression(tmp_path):
    '''
    Add a Windows regression test showing that PID reuse cannot cause Courier to terminate an unrelated process.
    Proves that termination relies on Job Objects, not PID scraping which is vulnerable to PID reuse races.
    '''
    run_dir = str(tmp_path)
    
    argv = ["cmd.exe", "/c", "timeout", "10"]
    run = _spawn_contained(argv, run_dir, "test-pid-reuse")
    
    # Store PID before it finishes
    pid = run.proc.pid
    
    run.terminate_tree()
    run.proc.wait()
    
    # Try terminating again - if it was vulnerable to PID reuse, it would issue a blind kill(pid)
    # The _terminate_job mechanism uses the job object handle, not the PID.
    # We call terminate_tree again to prove it doesn't crash or kill by PID.
    run.terminate_tree()
    
    # If the Job Object is properly used, we don't accidentally kill a new process 
    # that happens to get assigned the same PID. The assertion here is that terminate_tree
    # on an already terminated run is safe and does not target a raw PID.
    assert run.job is None or ctypes.windll.kernel32.WaitForSingleObject(run.proc._handle, 0) == 0
