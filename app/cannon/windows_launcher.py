"""Windows launcher for Courier Symphony Cannon.

Starts the background Cannon HTTP server on port 8768 if not already running,
waits for readiness, and opens the Cannon dashboard in the default Windows browser.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

try:
    import msvcrt
except ImportError:
    msvcrt = None

try:
    import fcntl
except ImportError:
    fcntl = None

ROOT = Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:8768"
URL = BASE + "/cannon"


def ready() -> bool:
    try:
        with urlopen(BASE + "/api/identity", timeout=0.5) as response:
            identity = json.load(response)
        if identity != {"app": "Courier Symphony V2", "root": str(ROOT)}:
            raise RuntimeError("Port 8768 belongs to a different application")
        with urlopen(URL, timeout=0.5) as response:
            return response.status == 200
    except (URLError, TimeoutError, OSError):
        return False


def open_browser(url: str) -> None:
    if sys.platform == "win32":
        try:
            os.startfile(url)
            return
        except AttributeError:
            pass
        subprocess.run(["cmd.exe", "/c", "start", "", url], check=True, timeout=10)
    else:
        subprocess.run(["/usr/bin/open", url], check=True, timeout=10)


def open_cannon() -> int:
    if ready():
        open_browser(URL)
        return 0

    creationflags = 0
    popen_kwargs = {}
    if sys.platform == "win32":
        creationflags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        )
        popen_kwargs["creationflags"] = creationflags
    else:
        popen_kwargs["start_new_session"] = True

    process = subprocess.Popen(
        [sys.executable, str(ROOT / "app/server.py"), "--cannon-only", "--port", "8768"],
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        **popen_kwargs,
    )

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if ready():
            open_browser(URL)
            return 0
        if process.poll() is not None:
            raise RuntimeError("Cannon exited before HTTP readiness")
        time.sleep(0.1)
    raise RuntimeError("Cannon did not become ready within 10 seconds")


def acquire_launch_lock(lock_file) -> None:
    deadline = time.monotonic() + 12
    while True:
        try:
            if msvcrt is not None:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                return
            elif fcntl is not None:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            else:
                return
        except (BlockingIOError, OSError):
            if time.monotonic() >= deadline:
                raise RuntimeError("Another Cannon launch has not finished")
            time.sleep(0.1)


def release_launch_lock(lock_file) -> None:
    try:
        if msvcrt is not None:
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        elif fcntl is not None:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
    except Exception:
        pass


def main() -> int:
    directory = Path.home() / ".courier"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "cannon-launch.lock").open("a+b") as lock:
        acquire_launch_lock(lock)
        try:
            return open_cannon()
        finally:
            release_launch_lock(lock)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
