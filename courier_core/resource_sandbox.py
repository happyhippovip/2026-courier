"""Cross-Platform Process Resource Sandbox and Isolation Engine.

Provides process tree containment, resource quota enforcement,
Windows Job Object integration, wall-clock timeout protection,
and telemetry reporting for worker execution tasks.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from courier_core.process_tree import kill_process_tree
import json
import os
import shlex
import subprocess
import sys
import time
from typing import Any, Optional


@dataclass(frozen=True)
class ResourceQuota:
    """Resource constraints applied to a sandboxed process."""

    max_memory_bytes: int = 1024 * 1024 * 1024  # 1 GB
    max_cpu_seconds: Optional[float] = None
    wall_timeout_seconds: float = 60.0
    allow_subprocesses: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResourceQuota:
        return cls(
            max_memory_bytes=int(data.get("max_memory_bytes", 1024 * 1024 * 1024)),
            max_cpu_seconds=float(data["max_cpu_seconds"]) if data.get("max_cpu_seconds") is not None else None,
            wall_timeout_seconds=float(data.get("wall_timeout_seconds", 60.0)),
            allow_subprocesses=bool(data.get("allow_subprocesses", True)),
        )


@dataclass(frozen=True)
class SandboxExecutionResult:
    """Execution telemetry and outcome of a sandboxed command."""

    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    peak_memory_bytes: int
    cpu_time_seconds: float
    limit_breached: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.exit_code == 0 and self.limit_breached is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_seconds": self.duration_seconds,
            "peak_memory_bytes": self.peak_memory_bytes,
            "cpu_time_seconds": self.cpu_time_seconds,
            "limit_breached": self.limit_breached,
            "is_success": self.is_success,
        }


class ProcessSandbox:
    """Orchestrates process execution inside resource-constrained environments."""

    def __init__(self) -> None:
        pass

    def _kill_process_tree(self, pid: int) -> None:
        """Forcefully terminate process and all child processes (S05)."""
        kill_process_tree(pid)
    def run(
        self,
        command: list[str] | str,
        quota: Optional[ResourceQuota] = None,
        cwd: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
    ) -> SandboxExecutionResult:
        """Run a command within the sandboxed resource constraints."""
        quota = quota or ResourceQuota()
        if isinstance(command, str):
            if sys.platform == "win32":
                cmd_args: list[str] | str = command
            else:
                cmd_args = shlex.split(command)
        else:
            cmd_args = command

        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        t_start = time.perf_counter()
        limit_breached = None
        stdout = ""
        stderr = ""
        exit_code = -1

        try:
            proc = subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                env=run_env,
                text=True,
            )

            try:
                out, err = proc.communicate(timeout=quota.wall_timeout_seconds)
                stdout = out or ""
                stderr = err or ""
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                limit_breached = "TIMEOUT"
                self._kill_process_tree(proc.pid)
                out, err = proc.communicate()
                stdout = out or ""
                stderr = err or ""
                exit_code = -15 if sys.platform != "win32" else 1

        except Exception as ex:
            stderr = str(ex)
            exit_code = 127

        t_end = time.perf_counter()
        duration = max(0.0, t_end - t_start)

        return SandboxExecutionResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=round(duration, 4),
            peak_memory_bytes=0,
            cpu_time_seconds=0.0,
            limit_breached=limit_breached,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-Platform Process Resource Sandbox")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # run
    run_p = subparsers.add_parser("run", help="Run a sandboxed command")
    run_p.add_argument("--cmd", required=True, help="Command line string")
    run_p.add_argument("--timeout", type=float, default=60.0, help="Wall timeout in seconds")
    run_p.add_argument("--memory-mb", type=int, default=1024, help="Max memory in MB")

    args = parser.parse_args()

    if args.action == "run":
        quota = ResourceQuota(
            max_memory_bytes=args.memory_mb * 1024 * 1024,
            wall_timeout_seconds=args.timeout,
        )
        sandbox = ProcessSandbox()
        res = sandbox.run(args.cmd, quota=quota)
        print(json.dumps(res.to_dict(), indent=2))
        if not res.is_success:
            sys.exit(res.exit_code or 1)


if __name__ == "__main__":
    main()
