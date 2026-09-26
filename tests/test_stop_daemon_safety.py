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
