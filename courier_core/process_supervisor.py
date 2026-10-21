"""Autonomous Worker Auto-Recovery and Process Supervisor (P35)

Provides robust child-process lifecycle orchestration, crash detection,
exponential backoff recovery, and graceful shutdown timeouts for autonomous workers.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from courier_core.process_tree import kill_process_tree


class ProcessStatus(str, Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CRASHED = "CRASHED"
    RESTARTING = "RESTARTING"
    EXHAUSTED = "EXHAUSTED"


class RestartPolicy(str, Enum):
    NEVER = "NEVER"
    ON_FAILURE = "ON_FAILURE"
    ALWAYS = "ALWAYS"


@dataclass
class ManagedProcess:
    proc_id: str
    command: List[str]
    restart_policy: RestartPolicy = RestartPolicy.ON_FAILURE
    max_restarts: int = 3
    restart_count: int = 0
    status: ProcessStatus = ProcessStatus.STOPPED
    exit_code: Optional[int] = None
    popen: Optional[subprocess.Popen] = None
    last_start_time: float = 0.0
    next_restart_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proc_id": self.proc_id,
            "command": list(self.command),
            "restart_policy": self.restart_policy.value,
            "max_restarts": self.max_restarts,
            "restart_count": self.restart_count,
            "status": self.status.value,
            "exit_code": self.exit_code,
        }


class ProcessSupervisor:
    """Oversees child process execution with automatic fault recovery and backoff."""

    def __init__(
        self,
        backoff_base_seconds: float = 0.5,
        max_backoff_seconds: float = 5.0,
    ) -> None:
        self.backoff_base_seconds = backoff_base_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self._processes: Dict[str, ManagedProcess] = {}
        self._lock = threading.Lock()

    def register_process(
        self,
        proc_id: str,
        command: List[str],
        restart_policy: RestartPolicy = RestartPolicy.ON_FAILURE,
        max_restarts: int = 3,
    ) -> ManagedProcess:
        with self._lock:
            proc = ManagedProcess(
                proc_id=proc_id,
                command=list(command),
                restart_policy=restart_policy,
                max_restarts=max_restarts,
            )
            self._processes[proc_id] = proc
            return proc

    def get_process(self, proc_id: str) -> Optional[ManagedProcess]:
        with self._lock:
            return self._processes.get(proc_id)

    def start_process(self, proc_id: str) -> bool:
        with self._lock:
            proc = self._processes.get(proc_id)
            if not proc:
                return False

            try:
                proc.popen = subprocess.Popen(
                    proc.command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                proc.status = ProcessStatus.RUNNING
                proc.last_start_time = time.time()
                return True
            except Exception:
                proc.status = ProcessStatus.CRASHED
                return False

    def stop_process(self, proc_id: str, timeout: float = 5.0) -> bool:
        with self._lock:
            proc = self._processes.get(proc_id)
            if not proc or not proc.popen:
                if proc:
                    proc.status = ProcessStatus.STOPPED
                return True

            p = proc.popen

        # Terminate process tree outside lock (S05)
        try:
            kill_process_tree(p, timeout_s=timeout)
        except Exception:
            pass

        with self._lock:
            proc.status = ProcessStatus.STOPPED
            proc.popen = None
            return True

    def poll_and_recover(self) -> Dict[str, ProcessStatus]:
        with self._lock:
            results: Dict[str, ProcessStatus] = {}

            for proc in self._processes.values():
                if proc.status == ProcessStatus.RUNNING and proc.popen:
                    ret = proc.popen.poll()
                    if ret is not None:
                        proc.exit_code = ret
                        proc.popen = None

                        if ret == 0:
                            if (
                                proc.restart_policy == RestartPolicy.ALWAYS
                                and proc.restart_count < proc.max_restarts
                            ):
                                self._trigger_restart(proc)
                            else:
                                proc.status = ProcessStatus.COMPLETED
                        else:
                            # Non-zero exit code
                            if (
                                proc.restart_policy in (RestartPolicy.ON_FAILURE, RestartPolicy.ALWAYS)
                                and proc.restart_count < proc.max_restarts
                            ):
                                self._trigger_restart(proc)
                            elif proc.restart_count >= proc.max_restarts:
                                proc.status = ProcessStatus.EXHAUSTED
                            else:
                                proc.status = ProcessStatus.CRASHED

                elif proc.status == ProcessStatus.RESTARTING:
                    if time.time() >= proc.next_restart_time:
                        self._spawn(proc)

                results[proc.proc_id] = proc.status

            return results

    def _trigger_restart(self, proc: ManagedProcess) -> None:
        proc.restart_count += 1
        backoff = min(
            self.max_backoff_seconds,
            self.backoff_base_seconds * (2 ** (proc.restart_count - 1)),
        )
        proc.next_restart_time = time.time() + backoff
        proc.status = ProcessStatus.RESTARTING
        if backoff <= 0.1:
            self._spawn(proc)

    def _spawn(self, proc: ManagedProcess) -> None:
        try:
            proc.popen = subprocess.Popen(
                proc.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            proc.status = ProcessStatus.RUNNING
            proc.last_start_time = time.time()
        except Exception:
            proc.status = ProcessStatus.CRASHED


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Process Supervisor CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run-once", help="Run processes defined in config and poll once")
    run_parser.add_argument("--config", required=True, help="Path to config JSON")

    args = parser.parse_args(argv)

    if args.command == "run-once":
        data = json.loads(Path(args.config).read_text(encoding="utf-8"))
        supervisor = ProcessSupervisor()

        for p_data in data.get("processes", []):
            policy = RestartPolicy(p_data.get("restart_policy", "ON_FAILURE"))
            supervisor.register_process(
                proc_id=p_data["proc_id"],
                command=p_data["command"],
                restart_policy=policy,
                max_restarts=p_data.get("max_restarts", 3),
            )
            supervisor.start_process(p_data["proc_id"])

        time.sleep(0.3)
        status_map = supervisor.poll_and_recover()

        print(json.dumps({
            "status": "SUCCESS",
            "results": {k: v.value for k, v in status_map.items()},
        }, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
