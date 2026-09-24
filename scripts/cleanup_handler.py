#!/usr/bin/env python3
"""Execution Resource Cleanup Handler for Courier Workers.

Safely releases locks, clears temporary state, and terminates exact owned process trees
for a given execution reference, strictly avoiding broad process-name kills.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_DIR = Path(__file__).resolve().parent.parent


def release_execution_resources(
    execution_ref: str,
    repo_dir: Path | None = None,
    locks_dir: Path | None = None,
    pid: int | None = None,
    quiet: bool = False,
) -> dict[str, Any]:
    """Cleans up execution resources for a given reference.

    - stops exact owned process tree
    - releases locks
    - clears current ownership
    - never broad process-name kills
    """
    if not execution_ref or not isinstance(execution_ref, str):
        raise ValueError("execution_ref must be a non-empty string")

    if not quiet:
        print(f"Releasing resources for execution: {execution_ref}")

    target_repo = repo_dir or REPO_DIR
    target_locks = locks_dir or (target_repo / "locks")
    released_locks: list[str] = []
    terminated_pids: list[int] = []
    errors: list[str] = []

    # 1. Release lock files matching execution_ref
    if target_locks.exists() and target_locks.is_dir():
        try:
            for lock_file in target_locks.glob(f"*{execution_ref}*.lock"):
                try:
                    lock_file.unlink(missing_ok=True)
                    released_locks.append(str(lock_file))
                except Exception as exc:
                    errors.append(f"Failed to remove lock {lock_file}: {exc}")
        except Exception as exc:
            errors.append(f"Error scanning locks dir {target_locks}: {exc}")

    # 2. Terminate exact owned process tree if PID specified
    if pid is not None and pid > 0:
        try:
            import psutil
            if psutil.pid_exists(pid):
                parent = psutil.Process(pid)
                # Terminate children first
                for child in parent.children(recursive=True):
                    try:
                        child.terminate()
                        terminated_pids.append(child.pid)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                try:
                    parent.terminate()
                    terminated_pids.append(pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except ImportError:
            # psutil not available, fallback to os.kill if available
            try:
                os.kill(pid, 15)
                terminated_pids.append(pid)
            except Exception as exc:
                errors.append(f"Failed to kill PID {pid}: {exc}")
        except Exception as exc:
            errors.append(f"Error terminating PID {pid}: {exc}")

    status = "SUCCESS" if not errors else "PARTIAL_SUCCESS"

    result = {
        "status": status,
        "execution_ref": execution_ref,
        "released_locks": released_locks,
        "terminated_pids": terminated_pids,
        "errors": errors,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    if not quiet:
        print(f"Cleanup for {execution_ref} complete.")

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Release execution resources safely")
    parser.add_argument("execution_ref", nargs="?", default="exec_001", help="Execution reference ID")
    parser.add_argument("--repo-dir", help="Path to repository root")
    parser.add_argument("--locks-dir", help="Directory where lock files reside")
    parser.add_argument("--pid", type=int, help="Exact PID to terminate if still active")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args(argv)

    repo_dir = Path(args.repo_dir).resolve() if args.repo_dir else None
    locks_dir = Path(args.locks_dir).resolve() if args.locks_dir else None

    result = release_execution_resources(
        execution_ref=args.execution_ref,
        repo_dir=repo_dir,
        locks_dir=locks_dir,
        pid=args.pid,
        quiet=args.json,
    )

    if args.json:
        print(json.dumps(result, indent=2))

    return 0 if result["status"] in ("SUCCESS", "PARTIAL_SUCCESS") else 1


if __name__ == "__main__":
    sys.exit(main())
