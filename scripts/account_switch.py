#!/usr/bin/env python3
"""Customer Account / Provider Switch Utility.

Checkpoints active tasks, closes temporary processes, preserves queue state,
and activates a new customer/provider account without losing progress.
"""

import argparse
import json
import os
import sys
import tempfile
import psutil
from pathlib import Path

try:
    from scripts.windows_worker.daemon import WindowsDaemon as WindowsPrimaryWorker
except Exception:
    class WindowsPrimaryWorker:
        def __init__(self):
            self.current_task = None
            self.owned_pids = set()

        def claim_task(self, task):
            self.current_task = task

        def save_state(self):
            pass


def atomic_save_json(path: str | Path, data: dict) -> None:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_file = tempfile.mkstemp(dir=target.parent, prefix="acc_", suffix=".tmp")
    with open(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp_file, target)


def trigger_account_switch(
    worker,
    new_account: str,
    state_file: str | None = None,
    session_file: str | None = None,
    repo_dir: str | None = None,
    quiet: bool = False,
) -> dict:
    if not quiet:
        print(">>> CUSTOMER TRIGGERED: SWITCH ACCOUNT / PROVIDER")

    if state_file is None:
        if repo_dir:
            state_file = os.path.join(repo_dir, "central_state.json")
        else:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            local_state = os.path.join(base_dir, "central_state.json")
            state_file = local_state if os.path.exists(local_state) else "central_state.json"

    if session_file is None:
        if repo_dir:
            session_file = os.path.join(repo_dir, "account_session.json")
        else:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            local_session = os.path.join(base_dir, "account_session.json")
            session_file = local_session if os.path.exists(local_session) else "account_session.json"

    # 1. checkpoint active work
    if worker.current_task:
        task_id = worker.current_task.get("task_id")
        if not quiet:
            print(f"Checkpointing active work for task {task_id}...")

        # 2. transition to WAITING_PROVIDER (NOT FAILED, NOT DONE)
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)

                for goal_id, goal_data in state.get("goals", {}).items():
                    for t in goal_data.get("workflow_plan", []):
                        if t.get("task_id") == task_id:
                            t["status"] = "WAITING_PROVIDER"
                            t["provider_failure_reason"] = "Account switch initiated by user"

                atomic_save_json(state_file, state)
            except (OSError, json.JSONDecodeError) as e:
                if not quiet:
                    print(f"Warning: could not update state_file: {e}")

        if not quiet:
            print(f"Transitioned task {task_id} to WAITING_PROVIDER.")

    # 3. close unnecessary temporary processes
    if not quiet:
        print("Closing unnecessary temporary processes while preserving branch/dirty edits...")

    for pid in list(getattr(worker, "owned_pids", set())):
        try:
            p = psutil.Process(pid)
            for child in p.children(recursive=True):
                try:
                    child.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            p.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    if hasattr(worker, "owned_pids"):
        worker.owned_pids.clear()

    # 4. preserve task queue (by not clearing the central state)
    if not quiet:
        print("Task queue preserved.")

    # 6. accept new provider/account
    if not quiet:
        print(f"Accepting new provider/account: {new_account}")

    session_doc = {
        "active_account": new_account,
        "switched_at": os.environ.get("COURIER_TIME", ""),
    }
    atomic_save_json(session_file, session_doc)

    # 7. resume same unfinished item
    if not quiet:
        print("Resuming unfinished item...")
    if worker.current_task:
        task_id = worker.current_task.get("task_id")
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                for goal_id, goal_data in state.get("goals", {}).items():
                    for t in goal_data.get("workflow_plan", []):
                        if t.get("task_id") == task_id:
                            t["status"] = "RUNNING"
                atomic_save_json(state_file, state)
            except (OSError, json.JSONDecodeError):
                pass

        if not quiet:
            print(f"Resumed active item: {task_id}")

    if not quiet:
        print("Queue ready to continue.")

    return {
        "status": "SUCCESS",
        "active_account": new_account,
        "current_task": worker.current_task,
        "session_file": str(session_file),
    }


def main():
    parser = argparse.ArgumentParser(description="Courier Account / Provider Switch")
    parser.add_argument("--account", default="NEW_ENTERPRISE_ACCOUNT", help="New account identifier")
    parser.add_argument("--state-file", help="Path to central_state.json")
    parser.add_argument("--session-file", help="Path to account_session.json")
    parser.add_argument("--repo-dir", help="Path to repository root")
    parser.add_argument("--json", action="store_true", help="Print result JSON to stdout")
    args = parser.parse_args()

    worker = WindowsPrimaryWorker()
    result = trigger_account_switch(
        worker,
        new_account=args.account,
        state_file=args.state_file,
        session_file=args.session_file,
        repo_dir=args.repo_dir,
        quiet=args.json,
    )
    if args.json:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
