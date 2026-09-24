#!/usr/bin/env python3
"""Courier Motor Starter.

Launches the core daemon services (server.app, courier_github_dispatcher, courier_watchdog)
with port conflict detection and background process separation on Windows.
"""

import argparse
import os
import socket
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", port)) == 0


def get_python_exe() -> str:
    if os.environ.get("COURIER_PYTHON"):
        return os.environ["COURIER_PYTHON"]
    return sys.executable


def launch(module: str, log_file: str, repo_dir: Path | None = None) -> subprocess.Popen:
    target_repo = repo_dir or REPO_DIR
    log_path = target_repo / "logs" / log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)

    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000008

    python_exe = get_python_exe()
    f = open(log_path, "a", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            [python_exe, "-u", "-m", module],
            stdout=f,
            stderr=f,
            cwd=str(target_repo),
            **kwargs
        )
        return proc
    finally:
        f.close()


def start_motor(repo_dir: Path | None = None, force: bool = False) -> bool:
    target_repo = repo_dir or REPO_DIR
    (target_repo / "logs").mkdir(parents=True, exist_ok=True)

    if not force and (is_port_in_use(8081) or is_port_in_use(8080)):
        print("Courier daemon appears to be running already (port 8081/8080 is in use). Refusing to start duplicate background jobs.")
        return False

    launch("server.app", "courier_daemon.log", repo_dir=target_repo)
    launch("scripts.courier_github_dispatcher", "courier_github_dispatcher.log", repo_dir=target_repo)
    launch("scripts.courier_watchdog", "courier_watchdog.log", repo_dir=target_repo)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start Courier motor background services")
    parser.add_argument("--repo-dir", help="Path to repository root")
    parser.add_argument("--force", action="store_true", help="Force start even if ports are in use")
    parser.add_argument("--check-ports", action="store_true", help="Check port status only")
    args = parser.parse_args(argv)

    repo_dir = Path(args.repo_dir).resolve() if args.repo_dir else None

    if args.check_ports:
        p8080 = is_port_in_use(8080)
        p8081 = is_port_in_use(8081)
        print(f"PORT_8080_IN_USE: {p8080}")
        print(f"PORT_8081_IN_USE: {p8081}")
        return 0

    started = start_motor(repo_dir=repo_dir, force=args.force)
    return 0 if started else 1


if __name__ == "__main__":
    sys.exit(main())
