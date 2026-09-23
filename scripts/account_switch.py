#!/usr/bin/env python3
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time

try:
    from scripts.orphan_task_reaper import (
        REPO_ROOT,
        get_canonical_state_path,
        atomic_save_json,
        safely_terminate_pid,
    )
except ImportError:
    from orphan_task_reaper import (
        REPO_ROOT,
        get_canonical_state_path,
        atomic_save_json,
        safely_terminate_pid,
    )

try:
    from scripts.windows_worker import WindowsPrimaryWorker
except ImportError:
    try:
        from windows_worker import WindowsPrimaryWorker
    except ImportError:
        WindowsPrimaryWorker = None

logger = logging.getLogger("account_switch")


def trigger_account_switch(worker, new_account: str, state_file=None, session_file=None) -> dict:
    print(">>> CUSTOMER TRIGGERED: SWITCH ACCOUNT / PROVIDER")
    s_path = get_canonical_state_path(state_file)
    sess_path = Path(session_file).resolve() if session_file else (REPO_ROOT / "account_session.json")

    task_id = None
    if worker and getattr(worker, "current_task", None):
        task_id = worker.current_task.get("task_id")

    # 1. Checkpoint active work & transition to WAITING_PROVIDER (NOT FAILED, NOT DONE)
    if task_id and s_path.exists():
        print(f"Checkpointing active work for task {task_id}...")
        try:
            with open(s_path, "r", encoding="utf-8") as f:
                state = json.load(f)

            found = False
            for goal_id, goal_data in state.get("goals", {}).items():
                if isinstance(goal_data, dict):
                    for t in goal_data.get("workflow_plan", []):
                        if isinstance(t, dict) and t.get("task_id") == task_id:
                            t["status"] = "WAITING_PROVIDER"
                            t["provider_failure_reason"] = "Account switch initiated by user"
                            t["checkpoint_timestamp"] = time.time()
                            found = True

            if found:
                atomic_save_json(s_path, state)
                print(f"Transitioned task {task_id} to WAITING_PROVIDER in canonical state.")
        except Exception as e:
            logger.warning(f"Could not checkpoint state for {task_id}: {e}")

    # 3. Close unnecessary temporary processes
    # 5. Preserve branch/dirty edits (never run git checkout or git reset here)
    print("Closing unnecessary temporary processes while preserving branch/dirty edits...")
    terminated_count = 0
    pids_to_clean = []
    if worker and hasattr(worker, "owned_pids"):
        pids_to_clean = list(worker.owned_pids)

    for pid in pids_to_clean:
        if safely_terminate_pid(pid):
            terminated_count += 1

    if worker and hasattr(worker, "owned_pids"):
        worker.owned_pids.clear()
        if hasattr(worker, "save_state"):
            try:
                worker.save_state()
            except Exception as e:
                logger.warning(f"Could not save worker state after clearing pids: {e}")

    # 4. Preserve task queue (central state is kept intact)
    print("Task queue preserved.")

    # 6. Accept new provider/account
    print(f"Accepting new provider/account: {new_account}")
    session_data = {
        "active_account": new_account,
        "updated_at": time.time(),
    }
    atomic_save_json(sess_path, session_data)

    # 7. Resume same unfinished item
    print("Resuming unfinished item...")
    if task_id and s_path.exists():
        try:
            with open(s_path, "r", encoding="utf-8") as f:
                state = json.load(f)

            resumed = False
            for goal_id, goal_data in state.get("goals", {}).items():
                if isinstance(goal_data, dict):
                    for t in goal_data.get("workflow_plan", []):
                        if isinstance(t, dict) and t.get("task_id") == task_id:
                            t["status"] = "RUNNING"
                            t.pop("provider_failure_reason", None)
                            t["resumed_at"] = time.time()
                            resumed = True

            if resumed:
                atomic_save_json(s_path, state)
                print(f"Resumed active item: {task_id}")
        except Exception as e:
            logger.warning(f"Could not resume task {task_id} in state: {e}")

    # 8. Continue rest of queue (queue is untouched)
    print("Queue ready to continue.")
    return {
        "success": True,
        "active_account": new_account,
        "resumed_task": task_id,
        "terminated_pids_count": terminated_count,
    }


if __name__ == "__main__":
    if WindowsPrimaryWorker is not None:
        worker = WindowsPrimaryWorker()
        worker.claim_task({"task_id": "WF-CANARY-STEP-1"})

        # Spawn a harmless sleep process for cross-platform simulation
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"], shell=False)
        worker.owned_pids.add(proc.pid)
        worker.save_state()

        res = trigger_account_switch(worker, "NEW_ENTERPRISE_ACCOUNT")
        print(f"Switch completed: {res}")
    else:
        print("WindowsPrimaryWorker not available in current environment.")
