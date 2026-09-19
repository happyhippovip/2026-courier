#!/usr/bin/env python3
"""Start the Visual Studio server without holding an agent task open.

This launcher exits as soon as it has either found a healthy existing server
or started a new server in its own process session.  It deliberately does not
stop or replace an existing listener; that keeps it safe to invoke from an
agent task and prevents duplicate Studio servers.
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


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


def launch_server(port: int) -> int:
    if port_is_listening(port):
        print(f"STUDIO_ALREADY_RUNNING port={port}")
        return 0

    log_path = Path(tempfile.gettempdir()) / "2026-courier-visual-studio.log"
    with log_path.open("a", encoding="utf-8") as log_file:
        creationflags = 0x08000000 if sys.platform == 'win32' else 0
        process = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT), "--port", str(port)],
            cwd=COURIER_DIR,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            close_fds=True,
            start_new_session=True, creationflags=creationflags,
        )

    # Importing the Chief/Courier state graph can take a few seconds on a cold
    # start.  This is bounded so an agent still receives a definitive result.
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if port_is_listening(port):
            print(f"STUDIO_STARTED pid={process.pid} port={port} log={log_path}")
            return 0
        if process.poll() is not None:
            print(f"STUDIO_START_FAILED exit_code={process.returncode} log={log_path}")
            return 1
        time.sleep(0.1)

    print(f"STUDIO_START_TIMEOUT pid={process.pid} port={port} log={log_path}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument(
        "--status",
        action="store_true",
        help="Only report whether the configured port is currently listening.",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    if args.status:
        print(f"STUDIO_LISTENING={port_is_listening(args.port)} port={args.port}")
        return 0 if port_is_listening(args.port) else 1
    return launch_server(args.port)


if __name__ == "__main__":
    raise SystemExit(main())
