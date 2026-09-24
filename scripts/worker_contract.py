#!/usr/bin/env python3
"""Canonical Worker Contract for Courier workers.

Defines lifecycle transitions and structured envelopes for registration, claiming,
execution, result delivery, and resource cleanup.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from typing import Any, Iterable

VALID_COST_CLASSES = {"FREE", "CHEAP", "EXPENSIVE", "PROHIBITIVE"}
VALID_RUNTIMES = {"windows", "linux", "mac", "hosted", "mock"}


class WorkerContract:
    def __init__(
        self,
        worker_id: str,
        capability_set: Iterable[str] | None = None,
        cost_class: str = "CHEAP",
        runtime_type: str = "windows",
    ):
        if not worker_id or not isinstance(worker_id, str):
            raise ValueError("worker_id must be a non-empty string")

        self.worker_id = worker_id
        caps = capability_set or []
        self.capability_set = sorted(list({str(c) for c in caps if c}))

        cost = cost_class.upper() if isinstance(cost_class, str) else "CHEAP"
        self.cost_class = cost if cost in VALID_COST_CLASSES else "CHEAP"

        rt = runtime_type.lower() if isinstance(runtime_type, str) else "windows"
        self.runtime_type = rt if rt in VALID_RUNTIMES else "windows"

    def _now(self) -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    def register(self, quiet: bool = False) -> dict[str, Any]:
        envelope = {
            "action": "REGISTER",
            "worker_id": self.worker_id,
            "capabilities": self.capability_set,
            "cost_class": self.cost_class,
            "runtime_type": self.runtime_type,
            "status": "REGISTERED",
            "timestamp": self._now(),
        }
        if not quiet:
            print(f"Worker {self.worker_id} registering...")
        return envelope

    def claim(self, task_id: str, quiet: bool = False) -> dict[str, Any]:
        if not task_id or not isinstance(task_id, str):
            raise ValueError("task_id must be a non-empty string")
        envelope = {
            "action": "CLAIM",
            "worker_id": self.worker_id,
            "task_id": task_id,
            "status": "CLAIMED",
            "timestamp": self._now(),
        }
        if not quiet:
            print(f"Worker {self.worker_id} claiming task {task_id}...")
        return envelope

    def execute(self, execution_ref: str, command: str | None = None, quiet: bool = False) -> dict[str, Any]:
        if not execution_ref or not isinstance(execution_ref, str):
            raise ValueError("execution_ref must be a non-empty string")
        envelope = {
            "action": "EXECUTE",
            "worker_id": self.worker_id,
            "execution_ref": execution_ref,
            "command": command,
            "status": "RUNNING",
            "timestamp": self._now(),
        }
        if not quiet:
            print(f"Executing {execution_ref}...")
        return envelope

    def result(
        self,
        status: str = "SUCCESS",
        artifacts: list[str] | None = None,
        details: dict[str, Any] | None = None,
        quiet: bool = False,
    ) -> dict[str, Any]:
        envelope = {
            "action": "RESULT",
            "worker_id": self.worker_id,
            "status": status.upper(),
            "artifacts": artifacts or [],
            "details": details or {},
            "timestamp": self._now(),
        }
        if not quiet:
            print("Returning structured outcome...")
        return envelope

    def cleanup(self, execution_ref: str | None = None, quiet: bool = False) -> dict[str, Any]:
        envelope = {
            "action": "CLEANUP",
            "worker_id": self.worker_id,
            "execution_ref": execution_ref,
            "status": "CLEANED",
            "timestamp": self._now(),
        }
        if not quiet:
            print("Cleaning exact task processes and resources...")
        return envelope

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "capability_set": self.capability_set,
            "cost_class": self.cost_class,
            "runtime_type": self.runtime_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkerContract:
        return cls(
            worker_id=data.get("worker_id", ""),
            capability_set=data.get("capability_set") or data.get("capabilities", []),
            cost_class=data.get("cost_class", "CHEAP"),
            runtime_type=data.get("runtime_type", "windows"),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Courier Worker Contract CLI")
    parser.add_argument("--worker-id", default="win_01", help="Unique worker identifier")
    parser.add_argument("--capabilities", nargs="*", default=["local_exec"], help="Worker capability set")
    parser.add_argument("--cost-class", default="CHEAP", choices=list(VALID_COST_CLASSES), help="Cost class")
    parser.add_argument("--runtime", default="windows", choices=list(VALID_RUNTIMES), help="Runtime OS/type")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--test-lifecycle", action="store_true", help="Run full lifecycle test")
    args = parser.parse_args(argv)

    try:
        w = WorkerContract(
            worker_id=args.worker_id,
            capability_set=args.capabilities,
            cost_class=args.cost_class,
            runtime_type=args.runtime,
        )
    except Exception as e:
        print(f"CONTRACT_INIT_ERROR: {e}", file=sys.stderr)
        return 1

    if args.test_lifecycle:
        quiet = args.json
        reg = w.register(quiet=quiet)
        clm = w.claim("task-001", quiet=quiet)
        exc = w.execute("exec-001", quiet=quiet)
        res = w.result("SUCCESS", ["artifact.json"], quiet=quiet)
        cln = w.cleanup("exec-001", quiet=quiet)

        if args.json:
            print(json.dumps({
                "worker": w.to_dict(),
                "lifecycle": [reg, clm, exc, res, cln],
            }, indent=2))
        return 0

    reg = w.register(quiet=args.json)
    if args.json:
        print(json.dumps(reg, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
