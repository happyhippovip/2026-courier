import subprocess
import sys
import time
import os
import signal
from pathlib import Path

def main():
    base_dir = Path(__file__).resolve().parent.parent
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # We rely on sys.executable which should be the venv's python if it was started properly
    python_exe = sys.executable
    
    # Environment
    env = os.environ.copy()
    env["UV_PROJECT_ENVIRONMENT"] = str(base_dir / ".venv_service")
    
    procs = []
    
    print("Courier Motor Supervisor starting...", flush=True)
    
    log_app = open(logs_dir / "courier_daemon.log", "a")
    procs.append(subprocess.Popen(
        [python_exe, "-u", "-m", "server.app"],
        cwd=str(base_dir),
        env=env,
        stdout=log_app,
        stderr=subprocess.STDOUT
    ))
    
    log_dispatcher = open(logs_dir / "courier_github_dispatcher.log", "a")
    procs.append(subprocess.Popen(
        [python_exe, "-u", "-m", "scripts.courier_github_dispatcher"],
        cwd=str(base_dir),
        env=env,
        stdout=log_dispatcher,
        stderr=subprocess.STDOUT
    ))
    
    log_watchdog = open(logs_dir / "courier_watchdog.log", "a")
    procs.append(subprocess.Popen(
        [python_exe, "-u", "-m", "scripts.courier_watchdog"],
        cwd=str(base_dir),
        env=env,
        stdout=log_watchdog,
        stderr=subprocess.STDOUT
    ))
    
    print("Courier Motor started. Monitoring processes...", flush=True)
    try:
        while True:
            for p in procs:
                ret = p.poll()
                if ret is not None:
                    print(f"A child process exited unexpectedly with code {ret}. Terminating others.", flush=True)
                    # Terminate all
                    for p_other in procs:
                        if p_other.poll() is None:
                            p_other.terminate()
                    sys.exit(1)
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping Courier Motor...", flush=True)
        for p in procs:
            if p.poll() is None:
                p.terminate()
        sys.exit(0)

if __name__ == "__main__":
    main()
