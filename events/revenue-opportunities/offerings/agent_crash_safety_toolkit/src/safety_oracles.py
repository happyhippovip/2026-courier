"""Autonomous Agent Crash-Safety Verification Oracles."""

import errno
import fcntl
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class AgentSafetyAuditor:
    """Verifies AI Agent workflows against common production failure modes."""

    @staticmethod
    def audit_pid_liveness(pid: int) -> bool:
        """Verifies if a target agent process is truly alive via Signal 0."""
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError as err:
            return err.errno == errno.EPERM

    @staticmethod
    def audit_file_lock_isolation(lock_path: Path) -> bool:
        """Tests non-blocking POSIX flock acquisition and race safety."""
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
            return True
        except (IOError, OSError):
            return False

    @staticmethod
    def audit_spend_firewall(requested_spend: float, allowed_limit: float = 0.0) -> bool:
        """Enforces hard ceiling spend protection."""
        return requested_spend <= allowed_limit

    @staticmethod
    def audit_heartbeat_staleness(last_heartbeat_ts: float, timeout_seconds: float = 30.0) -> bool:
        """Detects if an agent loop has stalled."""
        age = time.time() - last_heartbeat_ts
        return age <= timeout_seconds
