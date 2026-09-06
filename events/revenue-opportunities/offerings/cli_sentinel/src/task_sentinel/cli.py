#!/usr/bin/env python3
"""Task Sentinel CLI — Zero-Dependency Background Process Watchdog.

Commercial Pro Edition V1.0.0
Author: 2026-Courier Software Solutions
License: Dual MIT (Core) / Commercial Pro (Webhooks & Telemetry)
"""

from __future__ import annotations

import argparse
import datetime as dt
import errno
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def is_pid_alive(pid: int) -> bool:
    """True kernel PID liveness verification using signal 0."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError as err:
        if err.errno == errno.ESRCH:
            return False  # No such process
        elif err.errno == errno.EPERM:
            return True   # Alive, owned by different user
        return False


class LockManager:
    """Atomic POSIX file lock with PID registration and auto-cleanup."""

    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self._fd: Optional[int] = None

    def acquire(self, timeout_seconds: float = 0.0) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        start_t = time.time()
        
        while True:
            try:
                fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR, 0o644)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Acquired! Write current PID and timestamp
                os.ftruncate(fd, 0)
                payload = json.dumps({
                    "pid": os.getpid(),
                    "acquired_at": utc_now(),
                }) + "\n"
                os.write(fd, payload.encode("utf-8"))
                self._fd = fd
                return True
            except (IOError, OSError) as err:
                if self._fd is not None:
                    try:
                        os.close(self._fd)
                    except Exception:
                        pass
                    self._fd = None

                # Check if holding PID is dead (stale lock recovery)
                if self.is_stale():
                    try:
                        self.lock_path.unlink(missing_ok=True)
                    except Exception:
                        pass

                if timeout_seconds <= 0 or (time.time() - start_t) >= timeout_seconds:
                    return False
                time.sleep(0.05)

    def is_stale(self) -> bool:
        try:
            if not self.lock_path.exists():
                return False
            content = self.lock_path.read_text(encoding="utf-8")
            data = json.loads(content)
            holding_pid = data.get("pid")
            if holding_pid and not is_pid_alive(int(holding_pid)):
                return True
        except Exception:
            pass
        return False

    def release(self) -> None:
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None
            try:
                self.lock_path.unlink(missing_ok=True)
            except Exception:
                pass


class TaskSentinel:
    """Core process watchdog and heartbeat engine."""

    def __init__(self, state_file: Optional[Path] = None, webhook_url: Optional[str] = None):
        self.state_file = state_file or Path("task_sentinel_state.json")
        self.webhook_url = webhook_url

    def check_pid(self, pid: int) -> Dict[str, Any]:
        alive = is_pid_alive(pid)
        return {
            "pid": pid,
            "alive": alive,
            "checked_at": utc_now(),
            "status": "HEALTHY" if alive else "DEAD",
        }

    def update_heartbeat(self, heartbeat_file: Path, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        heartbeat_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "pid": os.getpid(),
            "timestamp": time.time(),
            "iso_time": utc_now(),
            "meta": meta or {},
        }
        temp = heartbeat_file.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, heartbeat_file)
        return data

    def verify_heartbeat(self, heartbeat_file: Path, stall_timeout: float = 30.0) -> Dict[str, Any]:
        if not heartbeat_file.is_file():
            return {
                "status": "MISSING",
                "stalled": True,
                "age_seconds": None,
                "checked_at": utc_now(),
            }
        try:
            data = json.loads(heartbeat_file.read_text(encoding="utf-8"))
            ts = data.get("timestamp", 0.0)
            pid = data.get("pid", 0)
            age = round(time.time() - ts, 2)
            pid_alive = is_pid_alive(pid) if pid else False
            stalled = age > stall_timeout or (pid and not pid_alive)

            status = "HEALTHY"
            if not pid_alive:
                status = "ORPHANED_PROCESS_DEAD"
            elif age > stall_timeout:
                status = "STALLED_HEARTBEAT_GAP"

            res = {
                "status": status,
                "stalled": stalled,
                "age_seconds": age,
                "pid": pid,
                "pid_alive": pid_alive,
                "checked_at": utc_now(),
            }

            if stalled and self.webhook_url:
                self.send_webhook_alert(f"Task Sentinel Alert: Process {pid} {status} (Age: {age}s)")

            return res
        except Exception as e:
            return {
                "status": "CORRUPTED",
                "stalled": True,
                "error": str(e),
                "checked_at": utc_now(),
            }

    def send_webhook_alert(self, message: str) -> bool:
        if not self.webhook_url:
            return False
        try:
            payload = json.dumps({"text": message, "timestamp": utc_now()}).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return resp.status in (200, 201, 204)
        except Exception:
            return False

    def watch_command(
        self,
        command: str,
        heartbeat_file: Optional[Path] = None,
        stall_timeout: float = 30.0,
        interval: float = 2.0,
    ) -> int:
        proc = subprocess.Popen(command, shell=True)
        pid = proc.pid
        print(f"[SENTINEL] Started process {pid}: '{command}'")

        try:
            while proc.poll() is None:
                if heartbeat_file:
                    hb = self.verify_heartbeat(heartbeat_file, stall_timeout=stall_timeout)
                    if hb["stalled"]:
                        print(f"[SENTINEL WARNING] Heartbeat stall detected: {hb['status']}")
                time.sleep(interval)

            returncode = proc.returncode
            print(f"[SENTINEL] Process {pid} terminated with exit code {returncode}")
            return returncode
        except KeyboardInterrupt:
            print(f"[SENTINEL] Terminating monitored process {pid}...")
            proc.terminate()
            proc.wait(timeout=5.0)
            return 130


def main() -> int:
    parser = argparse.ArgumentParser(description="Task Sentinel CLI — Zero-Dependency Background Process Watchdog")
    subparsers = parser.add_subparsers(dest="action", help="Action to execute")

    # check
    p_check = subparsers.add_parser("check", help="Verify kernel PID liveness")
    p_check.add_argument("pid", type=int, help="Process ID to check")

    # lock
    p_lock = subparsers.add_parser("lock", help="Test acquiring an atomic POSIX lock")
    p_lock.add_argument("lockfile", type=str, help="Path to lock file")
    p_lock.add_argument("--timeout", type=float, default=0.0, help="Acquisition timeout in seconds")

    # heartbeat
    p_hb = subparsers.add_parser("heartbeat", help="Update or verify heartbeat")
    p_hb.add_argument("heartbeat_file", type=str, help="Path to heartbeat JSON file")
    p_hb.add_argument("--update", action="store_true", help="Update heartbeat with current time/PID")
    p_hb.add_argument("--verify", action="store_true", help="Verify heartbeat freshness")
    p_hb.add_argument("--timeout", type=float, default=30.0, help="Stall timeout in seconds")
    p_hb.add_argument("--webhook", type=str, default=None, help="Webhook URL for alert dispatch")

    # watch
    p_watch = subparsers.add_parser("watch", help="Spawn and watch a background command")
    p_watch.add_argument("cmd", type=str, help="Shell command to run")
    p_watch.add_argument("--heartbeat-file", type=str, default=None, help="Heartbeat file to monitor")
    p_watch.add_argument("--timeout", type=float, default=30.0, help="Heartbeat stall timeout")
    p_watch.add_argument("--interval", type=float, default=2.0, help="Check interval in seconds")

    args = parser.parse_args()
    sentinel = TaskSentinel(webhook_url=getattr(args, "webhook", None))

    if args.action == "check":
        res = sentinel.check_pid(args.pid)
        print(json.dumps(res, indent=2))
        return 0 if res["alive"] else 1

    elif args.action == "lock":
        mgr = LockManager(Path(args.lockfile))
        ok = mgr.acquire(timeout_seconds=args.timeout)
        if ok:
            print(f"[SENTINEL] Acquired lock: {args.lockfile} (PID {os.getpid()})")
            mgr.release()
            return 0
        else:
            print(f"[SENTINEL ERROR] Failed to acquire lock: {args.lockfile}")
            return 1

    elif args.action == "heartbeat":
        hb_path = Path(args.heartbeat_file)
        if args.update:
            res = sentinel.update_heartbeat(hb_path)
            print(json.dumps(res, indent=2))
            return 0
        elif args.verify:
            res = sentinel.verify_heartbeat(hb_path, stall_timeout=args.timeout)
            print(json.dumps(res, indent=2))
            return 0 if not res["stalled"] else 2

    elif args.action == "watch":
        hb_path = Path(args.heartbeat_file) if args.heartbeat_file else None
        return sentinel.watch_command(args.cmd, heartbeat_file=hb_path, stall_timeout=args.timeout, interval=args.interval)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
