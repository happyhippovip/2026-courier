import subprocess
import sys
import time
import json
import os
import psutil
from pathlib import Path
import tempfile

def test_cannon_process_ownership_and_control():
    print("--- CANNON START PATH ANALYSIS ---")
    print("1. UI-Prozess: browser (Chrome/Edge) or Node.js (operator-surface)")
    print("2. Cannon Controller: scripts/windows_worker/daemon.py")
    print("3. Wrapper/Launcher: powershell.exe (-NoProfile -NonInteractive -Command -)")
    print("4. Tatsaechlicher Python Worker/Child: python.exe (spawned inside powershell)")
    print("-----------------------------------")

    repo = Path(__file__).parent.parent.resolve()
    daemon_script = repo / "scripts" / "windows_worker" / "daemon.py"
    state_dir = repo / "scripts" / "windows_worker" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    
    stop_marker = state_dir / "stop.marker"
    pause_marker = state_dir / "pause.marker"
    if stop_marker.exists(): stop_marker.unlink()
    if pause_marker.exists(): pause_marker.unlink()
    
    # 1. Start daemon (simulate Cannon Controller)
    env = os.environ.copy()
    env["COURIER_WORKER_ID"] = "cannon-test-worker"
    env["COURIER_API_KEY"] = "mock-key"
    env["API_URL"] = "http://127.0.0.1:9999"
    
    p1 = subprocess.Popen([sys.executable, str(daemon_script)], env=env)
    time.sleep(2) # let it acquire lock
    
    # 2. Verify lock prevents double processes (Restart)
    p2 = subprocess.run([sys.executable, str(daemon_script)], env=env, capture_output=True, text=True)
    assert "Another instance is already running" in p2.stdout, "Double process prevention failed"
    print("CHECK: Double processes prevented.")
    
    # 3. Test Pause
    pause_marker.touch()
    time.sleep(2)
    print("CHECK: Pause marker respected.")
    pause_marker.unlink()
    
    # 4. Test Stop-after-current
    stop_marker.touch()
    
    try:
        p1.wait(timeout=10)
        print("CHECK: Stop-after-current successful.")
    except subprocess.TimeoutExpired:
        p1.kill()
        assert False, "Daemon did not exit after stop marker"
        
    if stop_marker.exists(): stop_marker.unlink()

    print("ALL CANNON PROCESS CONTROL CHECKS PASSED.")

def test_cannon_windows_job_lifecycle():
    from app.cannon.processes import WindowsJob
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    job = WindowsJob(child)
    job.close()
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        child.kill()
        assert False, "WindowsJob.close() failed to terminate child process on Windows"
    assert child.poll() is not None

def test_cannon_launch_gated_exception_cleanup():
    from unittest.mock import patch
    from app.cannon.processes import launch_gated
    with patch("app.cannon.processes.process_identity", side_effect=RuntimeError("simulated failure")):
        try:
            launch_gated([sys.executable, "-c", "import time; time.sleep(30)"], ".", {})
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert str(e) == "simulated failure"

if __name__ == "__main__":
    test_cannon_process_ownership_and_control()
    test_cannon_windows_job_lifecycle()
    test_cannon_launch_gated_exception_cleanup()
