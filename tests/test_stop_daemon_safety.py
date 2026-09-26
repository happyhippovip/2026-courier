import subprocess
from pathlib import Path
import os
import sys

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "stop_daemon.sh"

def test_stop_daemon_does_not_kill_unrelated_process(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    pid_file = logs_dir / "courier_daemon.pid"
    
    # Write the current process PID (pytest), which is obviously NOT server/app.py
    pid_file.write_text(str(os.getpid()))
    
    # Run stop_daemon.sh with cwd=tmp_path
    out = subprocess.check_output(["bash", str(SCRIPT_PATH)], cwd=str(tmp_path), text=True)
    
    # The current process should NOT be killed (we are still running to check the output)
    assert "Stale PID file" in out
    assert not pid_file.exists()

def test_stop_daemon_kills_watchdog(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    pid_file = logs_dir / "courier_watchdog.pid"

    # Start a dummy process with "courier_watchdog.py" in its arguments
    dummy = subprocess.Popen([sys.executable, "-c", "import time, sys; sys.argv[0]='courier_watchdog.py'; time.sleep(10)"])
    try:
        pid_file.write_text(str(dummy.pid))
        out = subprocess.check_output(["bash", str(SCRIPT_PATH)], cwd=str(tmp_path), text=True)
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
