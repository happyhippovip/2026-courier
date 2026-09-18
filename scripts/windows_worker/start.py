import subprocess, sys, os
from pathlib import Path

# The daemon itself handles process-level locking robustly.
# We just launch the daemon detached.
base_dir = Path(__file__).parent
logs_dir = base_dir / 'logs'
logs_dir.mkdir(exist_ok=True)

daemon_path = base_dir / 'daemon.py'

print("Launching Windows worker daemon...")
with open(logs_dir / 'worker.log', 'a') as f:
    subprocess.Popen(
        [sys.executable, '-u', str(daemon_path)], 
        stdout=f, 
        stderr=f, 
        creationflags=0x08000008,
        cwd=str(base_dir)
    )
print("Daemon launched.")
