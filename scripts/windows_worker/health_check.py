#!/usr/bin/env python3
"""Windows Worker Health Check (parity with scripts/mac_worker/health_check.py)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATE_DIR = BASE_DIR / "state"


def check_scheduled_task() -> str:
    if os.name != "nt":
        return "UNSUPPORTED_OS"
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-ScheduledTask -TaskName 'CourierWindowsWorker*' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty State",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        out = (completed.stdout or "").strip()
        if out:
            return f"REGISTERED ({out.splitlines()[0].strip()})"
        return "NOT_REGISTERED"
    except Exception as exc:
        return f"CHECK_FAILED ({exc})"


def check_credentials() -> str:
    if os.environ.get("COURIER_API_KEY"):
        return "FOUND (env)"
    try:
        import keyring

        val = keyring.get_password("courier_worker", "courier_api_key")
        if val:
            return "FOUND (Windows Credential Manager)"
        return "NOT FOUND"
    except Exception:
        return "NOT FOUND (or inaccessible)"


def detect_capabilities() -> list[str]:
    caps = ["windows", "powershell"]
    if shutil.which("agy"):
        caps.append("antigravity")
    if shutil.which("gh"):
        try:
            out = subprocess.getoutput("gh extension list")
            if "copilot" in out:
                caps.append("copilot")
        except Exception:
            pass
    return caps


def run() -> dict[str, object]:
    print("=== Windows Worker Health Check ===")
    task_status = check_scheduled_task()
    print(f"Scheduled Task status: {task_status}")

    cred_status = check_credentials()
    print(f"Credential Manager credentials: {cred_status}")

    has_task_cp = (STATE_DIR / "current_task.json").exists()
    has_result_cp = (STATE_DIR / "current_result.json").exists()
    print(f"Pending Task Checkpoint: {'EXISTS' if has_task_cp else 'NONE'}")
    print(f"Pending Result Checkpoint: {'EXISTS' if has_result_cp else 'NONE'}")

    caps = detect_capabilities()
    print(f"Available Providers: {', '.join(caps)}")
    return {
        "scheduled_task": task_status,
        "credentials": cred_status,
        "pending_task_checkpoint": has_task_cp,
        "pending_result_checkpoint": has_result_cp,
        "capabilities": caps,
    }


if __name__ == "__main__":
    run()
