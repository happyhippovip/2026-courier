import subprocess, sys, os
from pathlib import Path

# Provide status check path to avoid spawn churn
base_dir = Path(__file__).parent
sys.path.insert(0, str(base_dir))
try:
    from status import get_pid
    if get_pid():
        print("Windows Worker HTTP Daemon is already running. Exiting.")
        sys.exit(0)
except ImportError:
    pass

# The daemon itself handles process-level locking robustly.
# We just launch the daemon detached.
logs_dir = base_dir / 'logs'
logs_dir.mkdir(exist_ok=True)

daemon_path = base_dir / 'daemon.py'

print("Launching Windows worker daemon...")
with open(logs_dir / 'worker.log', 'a') as f:
    # Handle creationflags for mac vs win (since we might test on mac)
    flags = 0x08000008 if os.name == 'nt' else 0
    subprocess.Popen(
        [sys.executable, '-u', str(daemon_path)], 
        stdout=f, 
        stderr=f, 
        creationflags=flags,
        cwd=str(base_dir)
    )
print("Daemon launched.")
