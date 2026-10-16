import os
import time
import subprocess
from pathlib import Path
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


def test_contained_run_windows_job_lifecycle_mock(monkeypatch):
    """Verify Windows job object termination contract without live Windows."""
    terminated_jobs = []
    closed_jobs = []

    monkeypatch.setattr("os.name", "nt")
    monkeypatch.setattr("courier_worker.host._terminate_job", lambda job: terminated_jobs.append(job))
    monkeypatch.setattr("courier_worker.host._close_job", lambda job: closed_jobs.append(job))

    class MockProc:
        def __init__(self):
            self.pid = 1234
            self._waited = False
        def poll(self):
            return 0 if self._waited else None
        def wait(self, timeout=None):
            self._waited = True
            return 0

    proc = MockProc()
    mock_job = object()
    run = ContainedRun(proc, mock_job, "out.log", "err.log")

    assert run.job is mock_job
    run.terminate_tree()

    assert terminated_jobs == [mock_job], "Job must be terminated on Windows"
    assert closed_jobs == [mock_job], "Job must be closed after termination"
    assert run.job is None, "Job handle must be cleared after termination"
    assert proc.poll() == 0, "Process must be waited and reaped"


def test_contained_run_windows_no_job(monkeypatch):
    """Verify Windows termination handles run without active job object."""
    terminated_jobs = []
    closed_jobs = []

    monkeypatch.setattr("os.name", "nt")
    monkeypatch.setattr("courier_worker.host._terminate_job", lambda job: terminated_jobs.append(job))
    monkeypatch.setattr("courier_worker.host._close_job", lambda job: closed_jobs.append(job))

    class MockProc:
        def __init__(self):
            self.pid = 5678
            self._waited = False
        def poll(self):
            return 0 if self._waited else None
        def wait(self, timeout=None):
            self._waited = True
            return 0

    proc = MockProc()
    run = ContainedRun(proc, None, "out.log", "err.log")
    run.terminate_tree()

    assert terminated_jobs == []
    assert closed_jobs == []
    assert run.job is None
    assert proc.poll() == 0


def test_windows_launcher_cs_single_instance_contract():
    """Verify CourierLauncher.cs enforces Local\\CourierV1 mutex and Job Object limits."""
    repo = Path(__file__).resolve().parent.parent
    cs_file = repo / "scripts" / "windows_worker" / "launcher" / "CourierLauncher.cs"
    assert cs_file.is_file(), "CourierLauncher.cs must exist"
    content = cs_file.read_text(encoding="utf-8")

    # Invariants mandated by V1_PRODUCT_QUALITY_BAR.md §9 (WINDOWS EXE):
    # 1. Mutex name must be Local\\CourierV1
    assert 'Mutex(true, "Local\\\\CourierV1", out createdNew)' in content
    # 2. Job Object must configure KILL_ON_JOB_CLOSE
    assert 'JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000' in content
    assert 'LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE' in content
    # 3. Process must be assigned to Job Object
    assert 'AssignProcessToJobObject(hJob, p.Handle)' in content
    # 4. Graceful ConsoleCtrlHandler PID cleanup
    assert 'SetConsoleCtrlHandler(ConsoleCtrlCheck, true)' in content
    assert 'launcher.pid' in content
    assert 'worker.pid' in content
    assert 'controller.pid' in content
    assert 'hub.pid' in content


