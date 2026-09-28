"""
Deliverable: Process Ownership
"""
import os
import time
from typing import List, Dict, Optional
from dataclasses import dataclass, field

@dataclass
class ProcessInfo:
    pid: int
    pgid: int
    port: Optional[int] = None
    started_at: float = field(default_factory=time.time)

class ProcessOwnershipManager:
    """
    Manages process ownership, orphan handling, foreign process detection,
    and timeout enforcement.
    """
    def __init__(self, run_id: str, timeout_seconds: int = 3600):
        self.run_id = run_id
        self.timeout_seconds = timeout_seconds
        self.owned_processes: Dict[int, ProcessInfo] = {}

    def register_process(self, pid: int, pgid: int, port: Optional[int] = None) -> None:
        """Register an owned process."""
        self.owned_processes[pid] = ProcessInfo(pid=pid, pgid=pgid, port=port)

    def detect_foreign_processes(self, external_pids: List[int]) -> List[int]:
        """Detect processes that are not owned by this run."""
        return [pid for pid in external_pids if pid not in self.owned_processes]

    def check_timeouts(self) -> List[int]:
        """Identify processes that have exceeded the timeout limit."""
        now = time.time()
        timed_out = []
        for pid, info in self.owned_processes.items():
            if (now - info.started_at) > self.timeout_seconds:
                timed_out.append(pid)
        return timed_out

    def plan_orphan_handling(self) -> Dict[str, List[int]]:
        """
        Identify orphans. Note: as per constraints, no actual process manipulation
        is performed. This just simulates/plans the cleanup.
        """
        # Simulated orphan detection
        orphans = [pid for pid, info in self.owned_processes.items() if info.pgid == 1]
        return {"orphans_to_terminate": orphans}

    def plan_owned_cleanup(self) -> List[int]:
        """
        Plan the cleanup of all owned processes. No processes are killed here.
        """
        return list(self.owned_processes.keys())
