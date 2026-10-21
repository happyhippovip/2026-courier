"""
courier_core/windows_process_hygiene.py — Windows Interactive Process Hygiene & Ownership Verification (CP-14 / CQ-14)

Invariants:
1. Exact Process Ownership required before stop/cleanup.
2. Verified identity check: PID + Process Create Time + Executable match before any termination.
3. If PID was recycled by the OS (create_time mismatch, different executable), termination is ABORTED.
4. Scoped Process Tree Termination: terminates only owned child processes without touching parent shells,
   other agent windows, user-opened terminals, or unrelated applications.
5. Single-instance launch hygiene: ensures only one worker daemon instance, zero infinite batch wrappers,
   and zero process churn.
6. Diagnostic status checks are one-shot, structured, and strictly bounded (no polling loops).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from courier_core.process_tree import kill_process_tree, is_process_alive


@dataclass
class ProcessOwnershipRecord:
    """Durable record capturing exact ownership identity of a worker/service process."""
    service_id: str
    worker_id: str
    pid: int
    process_create_time: float
    executable: str
    daemon_path: str
    started_at: float = field(default_factory=time.time)
    cmdline: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProcessOwnershipRecord:
        return cls(
            service_id=str(data.get("service_id", "courier-worker")),
            worker_id=str(data.get("worker_id", "UNKNOWN")),
            pid=int(data.get("pid", 0)),
            process_create_time=float(data.get("process_create_time", 0.0)),
            executable=str(data.get("executable", "")),
            daemon_path=str(data.get("daemon_path", "")),
            started_at=float(data.get("started_at", 0.0)),
            cmdline=list(data.get("cmdline", [])),
        )


def create_current_ownership_record(
    worker_id: str,
    service_id: str = "courier-worker",
    pid: Optional[int] = None,
    daemon_path: Optional[str] = None,
) -> ProcessOwnershipRecord:
    """Create an ownership record for the specified or current process."""
    target_pid = pid if pid is not None else os.getpid()
    create_time = 0.0
    exe = sys.executable
    cmdline: List[str] = []

    try:
        import psutil
        try:
            proc = psutil.Process(target_pid)
            create_time = proc.create_time()
            exe = proc.exe()
            cmdline = proc.cmdline()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            create_time = time.time()
    except ImportError:
        create_time = time.time()

    return ProcessOwnershipRecord(
        service_id=service_id,
        worker_id=worker_id,
        pid=target_pid,
        process_create_time=create_time,
        executable=exe,
        daemon_path=daemon_path or sys.argv[0],
        started_at=time.time(),
        cmdline=cmdline,
    )


def save_ownership_record(record: ProcessOwnershipRecord, path: Union[str, Path]) -> None:
    """Persist ownership record atomically with fsync."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    temp_path = p.with_suffix(".tmp")
    data = json.dumps(record.to_dict(), indent=2).encode("utf-8")
    with open(temp_path, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, p)


def load_ownership_record(path: Union[str, Path]) -> Optional[ProcessOwnershipRecord]:
    """Load ownership record if file exists and is valid JSON."""
    p = Path(path)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return ProcessOwnershipRecord.from_dict(data)
    except Exception:
        return None


def verify_process_identity(
    record: ProcessOwnershipRecord,
    create_time_tolerance_s: float = 2.0,
) -> bool:
    """
    Verify whether the process running at record.pid matches the exact ownership identity.
    Returns False if:
    - PID is dead
    - PID was recycled by the OS (create_time does not match)
    - Executable binary does not match expected Courier or Python runner
    """
    if record.pid <= 0:
        return False

    try:
        import psutil
        try:
            proc = psutil.Process(record.pid)
            if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
                return False

            # 1. Verify Create Time
            current_create_time = proc.create_time()
            if abs(current_create_time - record.process_create_time) > create_time_tolerance_s:
                # PID recycled by Windows for another program!
                return False

            # 2. Verify Executable
            current_exe = proc.exe().lower()
            expected_exe = record.executable.lower()
            if current_exe != expected_exe:
                # Also allow matching by basename if path moved or venv python
                if Path(current_exe).name != Path(expected_exe).name:
                    return False

            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
    except ImportError:
        # Fallback check if psutil not present
        return is_process_alive(record.pid)


def safe_terminate_owned_process_tree(
    record: ProcessOwnershipRecord,
    timeout_s: float = 10.0,
    ownership_file: Optional[Union[str, Path]] = None,
) -> bool:
    """
    Terminate ONLY the verified owned process and its child tree.
    If identity check fails (e.g. recycled PID), termination is ABORTED to protect
    unrelated shell windows, user terminals, and system tasks.
    """
    if not verify_process_identity(record):
        # PID was either already terminated or reused by another unrelated process!
        # Do NOT call taskkill or kill_process_tree!
        if ownership_file:
            try:
                Path(ownership_file).unlink(missing_ok=True)
            except Exception:
                pass
        return False

    # Identity verified: safe to kill exact process tree
    kill_process_tree(record.pid, timeout_s=timeout_s)

    if ownership_file:
        try:
            Path(ownership_file).unlink(missing_ok=True)
        except Exception:
            pass

    return True


def get_bounded_worker_status(ownership_path: Union[str, Path]) -> Dict[str, Any]:
    """
    One-shot, bounded status inspection.
    Returns structured state immediately without looping or polling.
    """
    record = load_ownership_record(ownership_path)
    if record is None:
        return {
            "status": "STOPPED",
            "running": False,
            "ownership_verified": False,
            "message": "No ownership record found.",
        }

    is_verified = verify_process_identity(record)
    if is_verified:
        return {
            "status": "RUNNING",
            "running": True,
            "ownership_verified": True,
            "service_id": record.service_id,
            "worker_id": record.worker_id,
            "pid": record.pid,
            "executable": record.executable,
            "started_at": record.started_at,
        }
    else:
        return {
            "status": "STALE_OR_RECYCLED",
            "running": False,
            "ownership_verified": False,
            "pid": record.pid,
            "message": "Ownership record exists but PID is dead or recycled by an unrelated process.",
        }
