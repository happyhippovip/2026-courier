#!/usr/bin/env python3
import argparse
import signal
import sys
import time
import subprocess
from pathlib import Path

SHUTDOWN_REQUESTED = False

def handle_sigterm(signum, frame):
    global SHUTDOWN_REQUESTED
    print("Received termination signal, shutting down...", flush=True)
    SHUTDOWN_REQUESTED = True

def main():
    parser = argparse.ArgumentParser(description="Continuous daemon wrapper for Courier")
    parser.add_argument("--repo-dir", default=".", help="Repository root directory")
    parser.add_argument("--poll-interval", type=int, default=5, help="Polling interval in seconds")
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    repo_dir = Path(args.repo_dir).resolve()
    relay_script = repo_dir / "scripts" / "run_chief_relay_cycle.py"

    print(f"Starting Courier Daemon... Polling every {args.poll_interval}s", flush=True)
    while not SHUTDOWN_REQUESTED:
        try:
            subprocess.run(
                [sys.executable, str(relay_script), "--repo-dir", str(repo_dir)],
                check=False,
                capture_output=True,
                text=True
            )
        except Exception as e:
            print(f"Daemon cycle error: {e}", file=sys.stderr, flush=True)
        
        # Sleep loop that can be interrupted by signal
        for _ in range(args.poll_interval):
            if SHUTDOWN_REQUESTED:
                break
            time.sleep(1)

    print("Courier Daemon shutdown complete.", flush=True)

if __name__ == "__main__":
    main()
