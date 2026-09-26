import subprocess
import tempfile
from pathlib import Path
import os
import shutil

ROOT = Path("/Users/user/Downloads/courier_work/google_longrun/writer-worktree")

def test_stop_daemon_does_not_kill_unrelated_process(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    
    # Create logs dir
    (ROOT / "logs").mkdir(exist_ok=True)
    pid_file = ROOT / "logs" / "courier_daemon.pid"
    
    # Write the current process PID (pytest), which is obviously NOT server/app.py
    pid_file.write_text(str(os.getpid()))
    
    # Run stop_daemon.sh
    out = subprocess.check_output(["bash", "scripts/stop_daemon.sh"], text=True)
    
    # The current process should NOT be killed (we are still running to check the output)
    assert "Stale PID file" in out
    assert not pid_file.exists()

def test_stop_daemon_kills_watchdog(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    (ROOT / "logs").mkdir(exist_ok=True)
    pid_file = ROOT / "logs" / "courier_watchdog.pid"

    # Start a dummy process with "courier_watchdog.py" in its arguments
    import sys
    dummy = subprocess.Popen([sys.executable, "-c", "import time, sys; sys.argv[0]='courier_watchdog.py'; time.sleep(10)"])
    try:
        pid_file.write_text(str(dummy.pid))
        out = subprocess.check_output(["bash", "scripts/stop_daemon.sh"], text=True)
        assert "Courier Watchdog stopped" in out
        assert not pid_file.exists()

        # Ensure it was actually terminated
        assert dummy.wait(timeout=2) != 0
    finally:
        if dummy.poll() is None:
            dummy.kill()
            dummy.wait()
        if pid_file.exists():
            pid_file.unlink()
