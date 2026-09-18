import os, json, sys, tempfile
from pathlib import Path
from status import get_pid

pid = get_pid()
if pid:
    print(f"Stopping Courier Windows Worker (PID: {pid})...")
    # Graceful termination
    try:
        import subprocess
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        print("Stopped.")
    except Exception as e:
        print(f"Failed to stop: {e}")
else:
    print("Windows Worker is not running.")
