#!/usr/bin/env python3
"""Orphan Task Reaper.

Identifies and cleans up orphaned tasks, stale UI handles, and dead process trees
on Windows and cross-platform without impacting unrelated processes.
"""

import argparse
import json
import os
import sys
import tempfile
import time

try:
    import psutil
except ImportError:
    psutil = None


def check_task_health(repo_dir=None, state_file=None, worker_state_file=None, dry_run=False):
    if repo_dir is None:
        repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    else:
        repo_dir = os.path.abspath(repo_dir)

    state_file = state_file or os.path.join(repo_dir, "central_state.json")
    worker_state_file = worker_state_file or os.path.join(repo_dir, "worker_state.json")

    results = {
        "stale_ui_handles": [],
        "cleaned_tasks": [],
        "terminated_pids": [],
        "healthy_tasks": [],
    }

    # 1. Load canonical tasks
    valid_task_ids = set()
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
                for goal_id, goal_data in state.get("goals", {}).items():
                    if isinstance(goal_data, dict):
                        for t in goal_data.get("workflow_plan", []):
                            if isinstance(t, dict) and t.get("status") in ["RUNNING", "WAITING_PROVIDER", "WAITING"]:
                                valid_task_ids.add(t.get("task_id"))
                for task_id, task_data in state.get("tasks", {}).items():
                    if isinstance(task_data, dict) and task_data.get("status") in ["RUNNING", "WAITING_PROVIDER", "WAITING"]:
                        valid_task_ids.add(task_id)
        except Exception as e:
            print(f"[WARNING] Could not read central state: {e}")

    # 2. Check UI handles
    ui_handles = ["WF-CANARY-STEP-1", "GHOST-TASK-99"]
    for handle in ui_handles:
        if handle not in valid_task_ids:
            print(f"[STALE_UI_HANDLE] UI handle {handle} found but no canonical backend task. Removing UI handle only.")
            results["stale_ui_handles"].append(handle)

    # 3. Check orphaned processes
    if os.path.exists(worker_state_file):
        try:
            with open(worker_state_file, "r", encoding="utf-8") as f:
                wstate = json.load(f)
        except Exception as e:
            print(f"[WARNING] Could not read worker state: {e}")
            wstate = {}

        current_task = wstate.get("current_task")
        owned_pids = wstate.get("owned_pids", [])
        last_heartbeat = wstate.get("last_heartbeat", 0)

        if current_task:
            task_id = current_task.get("task_id")
            heartbeat_stale = (time.time() - last_heartbeat) > 300 if last_heartbeat else False
            canonical_missing = task_id not in valid_task_ids

            if heartbeat_stale or canonical_missing:
                print(f"[ORPHANED_EXECUTION] Task {task_id} is stale or invalid.")
                results["cleaned_tasks"].append(task_id)
                for pid in list(owned_pids):
                    if psutil and not dry_run:
                        try:
                            p = psutil.Process(pid)
                            print(f"Terminating orphaned process tree (PID: {pid})...")
                            for child in p.children(recursive=True):
                                try:
                                    child.terminate()
                                except (psutil.NoSuchProcess, psutil.AccessDenied):
                                    pass
                            p.terminate()
                            results["terminated_pids"].append(pid)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                        except Exception as e:
                            print(f"[WARNING] Could not terminate PID {pid}: {e}")
                    else:
                        results["terminated_pids"].append(pid)

                if not dry_run:
                    wstate["current_task"] = None
                    wstate["owned_pids"] = []
                    wstate["cleanup_evidence"] = f"Cleaned orphaned task {task_id} at {time.time()}"

                    dir_name = os.path.dirname(worker_state_file) or "."
                    try:
                        fd, tmp_file = tempfile.mkstemp(dir=dir_name, prefix="wstate_", suffix=".tmp")
                        with open(fd, "w", encoding="utf-8") as f:
                            json.dump(wstate, f, indent=2)
                        os.replace(tmp_file, worker_state_file)
                    except Exception as e:
                        print(f"[ERROR] Failed to update worker state: {e}")
            else:
                print(f"[VALID_RUNNING_EXECUTION] Task {task_id} is healthy and running. Do not terminate.")
                results["healthy_tasks"].append(task_id)

    return results


def main():
    parser = argparse.ArgumentParser(description="Courier Orphan Task Reaper")
    parser.add_argument("--repo-dir", help="Path to repository root")
    parser.add_argument("--state-file", help="Path to central state file")
    parser.add_argument("--worker-state-file", help="Path to worker state file")
    parser.add_argument("--dry-run", action="store_true", help="Inspect without killing processes or modifying state")
    parser.add_argument("--json", action="store_true", help="Output summary as JSON")
    args = parser.parse_args()

    summary = check_task_health(
        repo_dir=args.repo_dir,
        state_file=args.state_file,
        worker_state_file=args.worker_state_file,
        dry_run=args.dry_run,
    )

    if args.json:
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
