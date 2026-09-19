"""Short-lived macOS launcher: reuse Cannon, never wait for its lifetime."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:8768"
URL = BASE + "/cannon"


def ready():
    try:
        with urlopen(BASE + "/api/identity", timeout=0.5) as response:
            identity = json.load(response)
        if identity != {"app": "Courier Symphony V2", "root": str(ROOT)}:
            raise RuntimeError("Port 8768 belongs to a different application")
        with urlopen(URL, timeout=0.5) as response:
            return response.status == 200
    except (URLError, TimeoutError, OSError):
        return False


def open_cannon():
    if ready():
        subprocess.run(["/usr/bin/open", URL], check=True, timeout=10)
        return 0
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "app/server.py"), "--cannon-only", "--port", "8768"],
        cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, start_new_session=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    # The assertion ends with this exact server, not with the launcher/app.
    subprocess.Popen(
        ["/usr/bin/caffeinate", "-i", "-s", "-w", str(process.pid)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, start_new_session=True)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if ready():
            subprocess.run(["/usr/bin/open", URL], check=True, timeout=10)
            return 0
        if process.poll() is not None:
            raise RuntimeError("Cannon exited before HTTP readiness")
        time.sleep(0.1)
    raise RuntimeError("Cannon did not become ready within 10 seconds")


def main():
    directory = Path.home() / ".courier"
    directory.mkdir(exist_ok=True)
    with (directory / "cannon-launch.lock").open("a") as lock:
        deadline = time.monotonic() + 12
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Another Cannon launch has not finished")
                time.sleep(0.1)
        return open_cannon()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
