#!/usr/bin/env python3
"""Start the Visual Studio server without holding an agent task open.

This launcher exits as soon as it has either found a healthy existing server
or started a new server in its own process session. It deliberately does not
stop or replace an existing listener; that keeps it safe to invoke from an
agent task and prevents duplicate Studio servers.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
SERVER_SCRIPT = SCRIPTS_DIR / "run_visual_studio_server.py"
STARTUP_TIMEOUT_SECONDS = 15.0


def port_is_listening(port: int) -> bool:
    """Return whether a local TCP listener accepts a connection."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def launch_server(
    port: int,
    repo_dir: Path | None = None,
    timeout: float = STARTUP_TIMEOUT_SECONDS,
    quiet: bool = False,
) -> dict[str, Any]:
    if port_is_listening(port):
        if not quiet:
            print(f"STUDIO_ALREADY_RUNNING port={port}")
        return {"status": "ALREADY_RUNNING", "port": port, "exit_code": 0}

    target_repo = repo_dir or COURIER_DIR
    target_server = target_repo / "scripts" / "run_visual_studio_server.py"
    if not target_server.exists():
        target_server = SERVER_SCRIPT

    log_path = Path(tempfile.gettempdir()) / "2026-courier-visual-studio.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000008  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
        kwargs["close_fds"] = True

    python_exe = os.environ.get("COURIER_PYTHON") or sys.executable

    with log_path.open("a", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            [python_exe, str(target_server), "--port", str(port)],
            cwd=str(target_repo),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            **kwargs,
        )

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_is_listening(port):
            if not quiet:
                print(f"STUDIO_STARTED pid={process.pid} port={port} log={log_path}")
            return {"status": "STARTED", "pid": process.pid, "port": port, "log": str(log_path), "exit_code": 0}
        if process.poll() is not None:
            if not quiet:
                print(f"STUDIO_START_FAILED exit_code={process.returncode} log={log_path}")
            return {"status": "START_FAILED", "pid": process.pid, "port": port, "exit_code": process.returncode or 1, "log": str(log_path)}
        time.sleep(0.1)

    if not quiet:
        print(f"STUDIO_START_TIMEOUT pid={process.pid} port={port} log={log_path}")
    return {"status": "TIMEOUT", "pid": process.pid, "port": port, "exit_code": 1, "log": str(log_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument(
        "--status",
        action="store_true",
        help="Only report whether the configured port is currently listening.",
    )
    parser.add_argument("--repo-dir", help="Path to repository root")
    parser.add_argument("--timeout", type=float, default=STARTUP_TIMEOUT_SECONDS, help="Startup timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON status")
    args = parser.parse_args(argv)

    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    repo_dir = Path(args.repo_dir).resolve() if args.repo_dir else None

    if args.status:
        listening = port_is_listening(args.port)
        if args.json:
            print(json.dumps({"port": args.port, "listening": listening}))
        else:
            print(f"STUDIO_LISTENING={listening} port={args.port}")
        return 0 if listening else 1

    result = launch_server(args.port, repo_dir=repo_dir, timeout=args.timeout, quiet=args.json)
    if args.json:
        print(json.dumps(result, indent=2))

    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
