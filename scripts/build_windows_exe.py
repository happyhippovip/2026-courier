"""Package the Courier Desktop Hub as an unsigned Windows EXE.

PyInstaller runs only on Windows. Anywhere else the command skips and does
not create an executable. The spec lists the hidden imports and the static
files the hub reads from disk. Nothing is signed and nothing is deployed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import queue
import select
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "scripts" / "courier_hub_windows.spec"

REQUIRED_HIDDEN_IMPORTS = (
    "courier_hub",
    "courier_hub.server",
    "courier_hub.model",
    "courier_hub.kolibri_data",
    "courier_hub.mission_chip",
    "courier_core",
    "courier_core.build",
    "courier_core.journal",
    "courier_core.projection",
    "courier_core.events",
    "courier_core.state_machine",
)
REQUIRED_DATA = (
    ("courier_hub/static", "courier_hub/static"),
)

SKIP_REASON = (
    "Windows-EXE-Build nur auf Windows mit lokalem PyInstaller. "
    "Dieser Host ist {platform}. Es wird kein EXE erzeugt."
)


def audit_spec_text(text: str) -> list[str]:
    """Names the spec still owes. An empty list means the contract is present."""
    missing = []
    for name in REQUIRED_HIDDEN_IMPORTS:
        if name not in text:
            missing.append(name)
    for _source, dest in REQUIRED_DATA:
        if dest not in text:
            missing.append(dest)
    return missing


def build_windows_exe(dist_dir) -> dict:
    """Build CourierHub.exe. On any other OS, skip without writing an EXE."""
    dist = Path(dist_dir)
    if sys.platform != "win32":
        return {
            "built": False,
            "skipped": True,
            "reason": SKIP_REASON.format(platform=sys.platform),
            "exe": None,
        }
    if importlib.util.find_spec("PyInstaller") is None and shutil.which("pyinstaller") is None:
        return {
            "built": False,
            "skipped": True,
            "reason": "PyInstaller ist nicht installiert. Es wird kein EXE erzeugt.",
            "exe": None,
        }
    missing = audit_spec_text(SPEC_PATH.read_text(encoding="utf-8"))
    if missing:
        raise RuntimeError("spec is missing " + ", ".join(missing))
    dist.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--distpath", str(dist), "--workpath", str(dist / "work"),
        str(SPEC_PATH),
    ]
    completed = subprocess.run(command, cwd=str(ROOT), check=False)
    exe = dist / "CourierHub.exe"
    if completed.returncode != 0 or not exe.is_file():
        raise RuntimeError("PyInstaller did not produce CourierHub.exe")
    return {"built": True, "skipped": False, "reason": "", "exe": str(exe)}


def stop_process_group(proc: subprocess.Popen) -> None:
    """Stop proc and every process in its group. Returns after the leader is gone."""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True, check=False,
        )
    else:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        # The leader can exit on SIGTERM while a child in the same group is
        # still alive. Escalate so that child does not outlive the stop.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def smoke_hub(command, *, home, env=None, cwd=None, timeout=15.0) -> dict:
    """Start the hub, GET /hub/api/status, then stop the process group."""
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        list(command),
        cwd=str(cwd) if cwd is not None else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        url = _read_url(proc, timeout)
        request = urllib.request.Request(url.rstrip("/") + "/hub/api/status")
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status != 200:
                raise RuntimeError(f"hub status HTTP {response.status}")
            body = json.loads(response.read().decode("utf-8"))
        if not isinstance(body, dict) or "controller" not in body:
            raise RuntimeError("hub status has no controller field")
        return body
    finally:
        stop_process_group(proc)


def _read_url(proc: subprocess.Popen, timeout: float) -> str:
    line_queue: queue.Queue[str] = queue.Queue()

    def _reader():
        try:
            for line in iter(proc.stdout.readline, ""):
                line_queue.put(line)
        except Exception:
            pass

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None and line_queue.empty():
            err = proc.stderr.read() if proc.stderr is not None else ""
            raise RuntimeError(f"hub exited {proc.returncode} before printing a URL: {err}")
        remaining = max(0.05, min(0.5, deadline - time.monotonic()))
        try:
            line = line_queue.get(timeout=remaining)
            if "http://127.0.0.1:" in line:
                return line.strip()
        except queue.Empty:
            continue
    raise RuntimeError("hub did not print http://127.0.0.1:")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build the unsigned Courier Desktop Hub EXE")
    parser.add_argument("--dist", default=str(ROOT / "dist" / "windows"))
    parser.add_argument("--check", action="store_true", help="audit the spec and do not build")
    parser.add_argument("--smoke", help="run the hub smoke against this executable or python -m path")
    parser.add_argument("--home", default="")
    args = parser.parse_args(argv)
    if args.check:
        missing = audit_spec_text(SPEC_PATH.read_text(encoding="utf-8"))
        if missing:
            print("SPEC MISSING: " + ", ".join(missing))
            return 1
        print("SPEC OK")
        return 0
    if args.smoke:
        home = Path(args.home) if args.home else Path(os.environ.get("TEMP", "/tmp")) / "courier-hub-smoke"
        body = smoke_hub(
            [args.smoke, "--home", str(home), "--controller", "http://127.0.0.1:9",
             "--port", "0", "--print-url"],
            home=home,
        )
        print(json.dumps(body, sort_keys=True))
        return 0
    result = build_windows_exe(args.dist)
    if result["skipped"]:
        print("SKIP: " + result["reason"])
        return 2
    print(result["exe"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
