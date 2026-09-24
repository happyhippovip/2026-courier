#!/usr/bin/env python3
"""Agent Session Manager.

Tracks, audits, and safely cleans up background monitor processes and agent sessions
without collateral damage to unrelated processes.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DEFAULT_REPO_DIR = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY_FILE = DEFAULT_REPO_DIR / ".agents" / "state" / "background_monitors.json"


def _get_registry_path(custom_path=None):
    if custom_path:
        return Path(custom_path).resolve()
    return DEFAULT_REGISTRY_FILE


def _load(registry_path=None):
    reg = _get_registry_path(registry_path)
    if not reg.exists():
        return {}
    try:
        with open(reg, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data, registry_path=None):
    reg = _get_registry_path(registry_path)
    reg.parent.mkdir(parents=True, exist_ok=True)
    dir_name = str(reg.parent)
    fd, tmp_file = tempfile.mkstemp(dir=dir_name, prefix="reg_", suffix=".tmp")
    with open(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_file, str(reg))


def get_process_info(pid):
    if os.name == "nt":
        try:
            import psutil
            p = psutil.Process(int(pid))
            return f"{p.create_time():.3f}:{' '.join(p.cmdline())}"
        except Exception:
            return None
    try:
        out = subprocess.check_output(["ps", "-p", str(pid), "-o", "lstart=,args="], stderr=subprocess.DEVNULL).decode().strip()
        if not out:
            return None
        return out
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def register_task(pid, owner, purpose, registry_path=None):
    data = _load(registry_path)
    if owner not in data:
        data[owner] = []

    info = get_process_info(pid)
    if not info:
        return False

    data[owner].append({
        "pid": pid,
        "purpose": purpose,
        "proc_info": info,
    })
    _save(data, registry_path)
    return True


def kill_pid(pid):
    if os.name == "nt":
        try:
            import psutil
            p = psutil.Process(int(pid))
            for child in p.children(recursive=True):
                try:
                    child.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            p.terminate()
            try:
                p.wait(timeout=3)
            except psutil.TimeoutExpired:
                p.kill()
                p.wait(timeout=1)
            return True
        except (ImportError, Exception):
            try:
                os.kill(int(pid), signal.SIGTERM)
                return True
            except OSError:
                return False
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):  # 3 seconds
            try:
                os.kill(pid, 0)
                time.sleep(0.1)
            except OSError:
                return True
        os.kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))
        return True
    except OSError:
        return False


def cleanup_session(owner, registry_path=None):
    data = _load(registry_path)
    if owner not in data:
        return 0

    killed_count = 0
    for task in data[owner]:
        pid = task["pid"]
        info = get_process_info(pid)
        # Verify it's the exact same process (start time matches)
        if info and info == task.get("proc_info"):
            if kill_pid(pid):
                killed_count += 1

    del data[owner]
    _save(data, registry_path)
    return killed_count


def audit_orphans(registry_path=None):
    """Removes dead processes from the registry without killing active ones."""
    data = _load(registry_path)
    changed = False
    for owner, tasks in list(data.items()):
        alive_tasks = []
        for task in tasks:
            pid = task["pid"]
            info = get_process_info(pid)
            if info and info == task.get("proc_info"):
                alive_tasks.append(task)
            else:
                changed = True

        if alive_tasks:
            data[owner] = alive_tasks
        else:
            del data[owner]
            changed = True

    if changed:
        _save(data, registry_path)


def main():
    parser = argparse.ArgumentParser(description="Agent Session Manager")
    parser.add_argument("action", choices=["register", "cleanup", "audit"], help="Action to perform")
    parser.add_argument("--pid", type=int, help="Process ID to register")
    parser.add_argument("--owner", help="Owner identifier")
    parser.add_argument("--purpose", help="Task purpose")
    parser.add_argument("--registry-path", help="Custom path to registry file")
    args = parser.parse_args()

    if args.action == "register":
        if not args.pid or not args.owner or not args.purpose:
            print("Error: --pid, --owner, and --purpose are required for register.")
            sys.exit(1)
        if register_task(args.pid, args.owner, args.purpose, args.registry_path):
            print(f"Registered {args.pid} to {args.owner}")
        else:
            print("Process not found")
    elif args.action == "cleanup":
        if not args.owner:
            print("Error: --owner is required for cleanup.")
            sys.exit(1)
        killed = cleanup_session(args.owner, args.registry_path)
        print(f"Killed {killed} tasks for {args.owner}")
    elif args.action == "audit":
        audit_orphans(args.registry_path)
        print("Audit complete")


if __name__ == "__main__":
    main()
