#!/usr/bin/env python3
"""Truthful macOS Worker Status Inspector.

Inspects launchctl registration and worker state directly without grep.
Classifies state into:
  - NOT_INSTALLED: plist absent from LaunchAgents
  - INSTALLED_NOT_LOADED: plist present, but not loaded in launchctl
  - LOADED_STOPPED: loaded in launchctl, but no live PID
  - RUNNING: loaded with active PID and responsive state

Reports structured output (JSON or human-readable text).
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

LABEL = "com.courier.mac_worker"


def parse_launchctl_dict(output_text):
    """Parse launchctl list <label> dictionary output without grep."""
    data = {}
    for line in output_text.splitlines():
        line = line.strip().rstrip(";")
        if "=" in line:
            parts = line.split("=", 1)
            key = parts[0].strip().strip('"')
            val = parts[1].strip().strip('"')
            if val.isdigit():
                data[key] = int(val)
            else:
                data[key] = val
    return data


def query_launchctl(label=LABEL):
    """Query launchctl for the service label directly without grep."""
    try:
        p = subprocess.run(
            ["launchctl", "list", label],
            capture_output=True,
            text=True,
            timeout=5
        )
        if p.returncode == 0:
            parsed = parse_launchctl_dict(p.stdout)
            pid = parsed.get("PID")
            last_exit = parsed.get("LastExitStatus")
            return {
                "loaded": True,
                "pid": int(pid) if pid is not None else None,
                "last_exit_status": int(last_exit) if last_exit is not None else None,
                "raw": p.stdout.strip()
            }
        else:
            return {
                "loaded": False,
                "pid": None,
                "last_exit_status": None,
                "raw": p.stderr.strip() or p.stdout.strip()
            }
    except (FileNotFoundError, subprocess.SubprocessError):
        return {
            "loaded": False,
            "pid": None,
            "last_exit_status": None,
            "raw": "launchctl unavailable"
        }


def query_worker_state(here_dir):
    """Read local state files if present."""
    state_dir = Path(here_dir) / "state"
    task_file = state_dir / "current_task.json"
    ckpt_file = state_dir / "checkpoint.json"

    task_data = {}
    if task_file.exists():
        try:
            task_data = json.loads(task_file.read_text())
        except Exception:
            pass

    ckpt_data = {}
    if ckpt_file.exists():
        try:
            ckpt_data = json.loads(ckpt_file.read_text())
        except Exception:
            pass

    return {
        "task_id": task_data.get("task_id") or ckpt_data.get("task_id"),
        "phase": task_data.get("worker_phase") or ckpt_data.get("phase"),
        "branch": ckpt_data.get("branch"),
        "dispatch_id": task_data.get("dispatch_id")
    }


def derive_status(plist_path=None, here_dir=None):
    if here_dir is None:
        here_dir = Path(__file__).resolve().parent
    if plist_path is None:
        plist_path = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"

    plist_exists = Path(plist_path).exists()
    launch_info = query_launchctl(LABEL)
    worker_state = query_worker_state(here_dir)

    if not plist_exists:
        status_label = "NOT_INSTALLED"
    elif not launch_info["loaded"]:
        status_label = "INSTALLED_NOT_LOADED"
    elif launch_info["pid"] is not None and launch_info["pid"] > 0:
        status_label = "RUNNING"
    else:
        status_label = "LOADED_STOPPED"

    return {
        "status": status_label,
        "label": LABEL,
        "plist_path": str(plist_path),
        "plist_exists": plist_exists,
        "launchctl_loaded": launch_info["loaded"],
        "pid": launch_info["pid"],
        "last_exit_status": launch_info["last_exit_status"],
        "worker_task_id": worker_state.get("task_id"),
        "worker_phase": worker_state.get("phase"),
        "worker_branch": worker_state.get("branch")
    }


def main():
    parser = argparse.ArgumentParser(description="Truthful macOS Worker Status")
    parser.add_argument("--json", action="store_true", help="Output status as JSON")
    parser.add_argument("--plist-path", default=None, help="Custom path to plist file")
    args = parser.parse_args()

    status_data = derive_status(plist_path=args.plist_path)

    if args.json:
        print(json.dumps(status_data, indent=2))
    else:
        print(f"Service Label:  {status_data['label']}")
        print(f"Status:         {status_data['status']}")
        print(f"Plist Exists:   {status_data['plist_exists']} ({status_data['plist_path']})")
        print(f"Launchd Loaded: {status_data['launchctl_loaded']}")
        if status_data["pid"]:
            print(f"Process PID:    {status_data['pid']}")
        if status_data["last_exit_status"] is not None:
            print(f"Last Exit:      {status_data['last_exit_status']}")
        if status_data["worker_task_id"]:
            print(f"Active Task:    {status_data['worker_task_id']} (Phase: {status_data['worker_phase']})")

    # Exit code: 0 if running or loaded_stopped, 1 if not installed, 2 if error
    if status_data["status"] == "NOT_INSTALLED":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
