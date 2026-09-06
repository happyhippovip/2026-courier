#!/usr/bin/env python3
"""Task Sentinel CLI — Zero-Dependency Background Worker Watchdog.

Standalone developer utility for monitoring background task runners,
kernel PID liveness, POSIX flock lease freshness, and orphan process cleanup.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class TaskSentinel:
    def __init__(self, heartbeat_max_gap_seconds: float = 30.0):
        self.heartbeat_max_gap = heartbeat_max_gap_seconds

    def check_pid_alive(self, pid: Optional[int]) -> bool:
        """Verifies true kernel PID liveness using signal 0."""
        if pid is None or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def inspect_worker_health(
        self,
        worker_id: str,
        pid: Optional[int],
        last_heartbeat_iso: Optional[str],
    ) -> Dict[str, Any]:
        """Evaluates worker liveness and heartbeat freshness."""
        now = dt.datetime.now(dt.timezone.utc)
        pid_alive = self.check_pid_alive(pid)

        heartbeat_fresh = False
        heartbeat_age_sec = None
        if last_heartbeat_iso:
            try:
                hb_time = dt.datetime.fromisoformat(last_heartbeat_iso)
                heartbeat_age_sec = (now - hb_time).total_seconds()
                if heartbeat_age_sec <= self.heartbeat_max_gap:
                    heartbeat_fresh = True
            except Exception:
                pass

        if pid_alive and heartbeat_fresh:
            status = "HEALTHY"
        elif pid_alive and not heartbeat_fresh:
            status = "STALLED_HEARTBEAT"
        elif not pid_alive and last_heartbeat_iso:
            status = "ORPHANED_DEAD_PID"
        else:
            status = "UNKNOWN"

        return {
            "worker_id": worker_id,
            "pid": pid,
            "pid_alive": pid_alive,
            "heartbeat_age_seconds": heartbeat_age_sec,
            "heartbeat_fresh": heartbeat_fresh,
            "status": status,
            "evaluated_at": utc_now(),
        }

    def try_acquire_flock_lease(self, lock_path: Path) -> Tuple[bool, Optional[int]]:
        """Attempts non-blocking POSIX flock acquisition."""
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True, fd
        except (BlockingIOError, PermissionError, OSError):
            return False, None


def main() -> int:
    parser = argparse.ArgumentParser(description="Task Sentinel CLI")
    parser.add_argument("--pid", type=int, help="Target worker PID")
    parser.add_argument("--worker-id", type=str, default="worker-01", help="Worker identifier")
    parser.add_argument("--heartbeat", type=str, help="Last heartbeat ISO timestamp")
    args = parser.parse_args()

    sentinel = TaskSentinel()
    res = sentinel.inspect_worker_health(args.worker_id, args.pid, args.heartbeat)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
