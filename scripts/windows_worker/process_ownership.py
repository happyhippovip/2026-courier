"""
scripts/windows_worker/process_ownership.py — Windows Worker Process Ownership CLI (CP-14 / CQ-14)

Provides bounded status inspection and verified identity-checked termination.
Guarantees zero collateral damage to unrelated shells, user-opened terminals, or editors.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Add repo root to sys.path so courier_core is importable
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from courier_core.windows_process_hygiene import (
    ProcessOwnershipRecord,
    create_current_ownership_record,
    get_bounded_worker_status,
    load_ownership_record,
    safe_terminate_owned_process_tree,
    save_ownership_record,
    verify_process_identity,
)


def get_default_ownership_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data) / "Courier"
    else:
        base = Path.home() / ".courier"
    base.mkdir(parents=True, exist_ok=True)
    return base / "worker_ownership.json"


def cmd_status(ownership_path: Path) -> int:
    status = get_bounded_worker_status(ownership_path)
    print(json.dumps(status, indent=2))
    return 0 if status.get("running") else 1


def cmd_stop(ownership_path: Path) -> int:
    record = load_ownership_record(ownership_path)
    if not record:
        print(f"No active ownership record found at {ownership_path}. Nothing to stop.")
        return 0

    print(f"Verifying process ownership for PID {record.pid} ({record.executable})...")
    if not verify_process_identity(record):
        print(f"SAFETY ABORT: PID {record.pid} is either dead or belongs to an unrelated recycled process.")
        print("Zero processes killed to prevent collateral shell/terminal damage.")
        ownership_path.unlink(missing_ok=True)
        return 0

    print(f"Ownership confirmed: terminating worker process tree for PID {record.pid}...")
    stopped = safe_terminate_owned_process_tree(record, timeout_s=5.0, ownership_file=ownership_path)
    if stopped:
        print(f"Successfully stopped Courier worker PID {record.pid}.")
    else:
        print(f"Failed or aborted termination for PID {record.pid}.")
    return 0


def cmd_record(ownership_path: Path, worker_id: str, pid: int) -> int:
    record = create_current_ownership_record(worker_id=worker_id, pid=pid)
    save_ownership_record(record, ownership_path)
    print(f"Saved ownership record for worker '{worker_id}' PID {pid} to {ownership_path}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Windows Worker Process Ownership CLI")
    parser.add_argument("command", choices=["status", "stop", "record"], help="Action to perform")
    parser.add_argument("--ownership-file", type=Path, default=None, help="Path to ownership JSON file")
    parser.add_argument("--worker-id", type=str, default="WINDOWS-WORKER", help="Worker identifier for record")
    parser.add_argument("--pid", type=int, default=os.getpid(), help="PID to record")

    args = parser.parse_args()
    ownership_path = args.ownership_file or get_default_ownership_path()

    if args.command == "status":
        return cmd_status(ownership_path)
    elif args.command == "stop":
        return cmd_stop(ownership_path)
    elif args.command == "record":
        return cmd_record(ownership_path, args.worker_id, args.pid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
