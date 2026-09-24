#!/usr/bin/env python3
"""Courier Verifier Starter.

Safely launches or verifies the background courier verifier service,
preventing duplicate verifier processes.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent


def is_verifier_running() -> bool:
    try:
        import psutil
        for p in psutil.process_iter(['name', 'cmdline']):
            cmdline = p.info.get('cmdline') or []
            if any('scripts.courier_verifier' in str(arg) or 'courier_verifier.py' in str(arg) for arg in cmdline):
                return True
    except Exception:
        pass
    return False


def launch_verifier(log_file: str = "verifier.log", repo_dir: Path | None = None, force: bool = False) -> bool:
    target_repo = repo_dir or REPO_DIR
    if not force and is_verifier_running():
        print("Courier verifier is already running. Refusing to launch duplicate background verifier.")
        return False

    log_path = target_repo / "scripts" / log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)

    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000008

    python_exe = os.environ.get("COURIER_PYTHON") or sys.executable
    with open(log_path, "a", encoding="utf-8") as f:
        subprocess.Popen(
            [python_exe, "-u", "-m", "scripts.courier_verifier"],
            stdout=f,
            stderr=f,
            cwd=str(target_repo),
            **kwargs
        )
    print(f"Launched verifier logging to {log_path}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start Courier Background Verifier")
    parser.add_argument("--repo-dir", help="Path to repository root")
    parser.add_argument("--log-file", default="verifier.log", help="Log file name in scripts/")
    parser.add_argument("--force", action="store_true", help="Launch even if another verifier is running")
    parser.add_argument("--check-only", action="store_true", help="Check if verifier is running without launching")
    args = parser.parse_args(argv)

    repo_dir = Path(args.repo_dir).resolve() if args.repo_dir else None

    if args.check_only:
        running = is_verifier_running()
        print(f"VERIFIER_RUNNING: {running}")
        return 0 if running else 1

    launch_verifier(log_file=args.log_file, repo_dir=repo_dir, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
