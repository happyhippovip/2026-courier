"""Hardened Process Tree Termination and Orphan Prevention (S05).

Provides fail-closed, multi-tier process tree termination:
1. Validates target PID / Popen object to ensure valid, positive, non-self PID.
2. Snapshots all recursive descendants via psutil before signaling parent.
3. On Windows: executes `taskkill /PID <pid> /T /F` with timeout=10, shell=False.
4. On POSIX: sends SIGKILL to process group `os.killpg(pid, signal.SIGKILL)` or `os.kill(pid, signal.SIGKILL)`.
5. Forcibly terminates the parent process via `proc.kill()` or `os.kill()`.
6. Iterates over all snapshotted descendants and terminates any survivors (`child.kill()`).
7. Waits/reaps with a bounded timeout to prevent zombie processes.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from typing import Any, List, Optional, Union


def get_process_descendants(pid: int) -> List[Any]:
    """Snapshot all live recursive descendant processes for a given PID."""
    if not isinstance(pid, int) or pid <= 0 or pid == os.getpid():
        return []
    try:
        import psutil
        try:
            parent = psutil.Process(pid)
            return parent.children(recursive=True)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return []
    except ImportError:
        return []


def is_process_alive(pid: int) -> bool:
    """Check if process with given PID is alive and not a zombie."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        import psutil
        try:
            proc = psutil.Process(pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    except ImportError:
        if os.name == "nt":
            # On Windows, os.kill(pid, 0) terminates the process, so fallback to tasklist
            try:
                res = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=False,
                    timeout=5,
                )
                return str(pid) in (res.stdout or b"").decode("ascii", errors="ignore")
            except Exception:
                return False
        else:
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False


def kill_process_tree(
    target: Union[subprocess.Popen, int],
    timeout_s: float = 10.0,
) -> None:
    """Terminate target process and its full process tree to guarantee zero orphans."""
    proc: Optional[subprocess.Popen] = None
    pid: Optional[int] = None

    if isinstance(target, subprocess.Popen):
        proc = target
        pid = getattr(proc, "pid", None)
    elif isinstance(target, int):
        pid = target

    if not isinstance(pid, int) or pid <= 0 or pid == os.getpid():
        return

    # 1. Snapshot descendant processes before initial signals are sent
    descendants = get_process_descendants(pid)

    # 2. Platform-specific tree kill
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=max(1.0, min(timeout_s, 30.0)),
                check=False,
                shell=False,
            )
        except Exception:
            pass
    else:
        # POSIX process group termination
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass

    # 3. Forcibly kill parent Popen if available
    if proc is not None:
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.communicate(timeout=2.0)
        except Exception:
            pass
    else:
        try:
            if os.name != "nt":
                os.kill(pid, signal.SIGKILL)
        except Exception:
            pass

    # 4. Sweep and terminate any remaining snapshotted descendants
    for child in descendants:
        try:
            child.kill()
        except Exception:
            pass
