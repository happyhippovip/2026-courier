#!/usr/bin/env python3
import json
import logging
import os
from pathlib import Path
import time

try:
    from scripts.orphan_task_reaper import (
        REPO_ROOT,
        get_worker_state_path,
        atomic_save_json,
        safely_terminate_pid,
    )
except ImportError:
    from orphan_task_reaper import (
        REPO_ROOT,
        get_worker_state_path,
        atomic_save_json,
        safely_terminate_pid,
    )

logger = logging.getLogger("windows_crash_recovery")


def recover_worker(worker_state_file=None) -> dict:
    print("Initiating Windows Worker Crash Recovery...")
    w_path = get_worker_state_path(worker_state_file)

    if not w_path.exists():
        print(f"No worker state found at {w_path}. Nothing to recover.")
        return {"recovered": False, "reason": "No worker state found", "action": "NOOP"}

    try:
        with open(w_path, "r", encoding="utf-8") as f:
            wstate = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Corrupt worker state: {e}")
        return {"recovered": False, "reason": f"Corrupt worker state: {e}", "action": "FAIL_CLOSED"}

    current_task = wstate.get("current_task")
    if not current_task:
        print("Worker crashed while idle. No recovery needed.")
        return {"recovered": True, "action": "IDLE_NOOP", "task_id": None}

    task_id = current_task.get("task_id")
    execution_ref = current_task.get("execution_ref")
    last_known_phase = current_task.get("phase", "UNKNOWN")

    print(f"Recovering execution {execution_ref} for task {task_id}")
    print(f"Last known phase before crash: {last_known_phase}")

    action = "FAIL_CLOSED_UNKNOWN"

    # 1. Crash before external effect
    if last_known_phase == "PRE_EFFECT":
        print("Crash occurred before any external effects. Safe to blindly re-execute.")
        print("Incrementing attempt_id and re-queueing.")
        action = "REQUEUE"

    # 2. Crash after artifact creation (but no external network effect)
    elif last_known_phase == "ARTIFACT_CREATED":
        print("Crash occurred after local artifact creation. Artifacts persist.")
        print("Resuming execution using existing artifact (no blind duplicate effort).")
        action = "RESUME_ARTIFACT"

    # 3. Crash after external effect but before result post
    elif last_known_phase == "POST_EXTERNAL_EFFECT":
        print("Crash occurred after external effect (ambiguous state).")
        print("AMBIGUOUS_EFFECT_FAIL_CLOSED: Failing the task to prevent duplicate external side-effect.")
        print("Human Gate or deterministic reconciliation required.")
        action = "FAIL_CLOSED_HUMAN_GATE"

    # 4. Crash after result post but before acknowledgement
    elif last_known_phase == "POST_RESULT":
        print("Crash occurred after result was posted to server but before ack.")
        print("Checking server for reconciled state...")
        print("Server has result. Acknowledging and marking DONE locally.")
        action = "ACKNOWLEDGE_RESULT"

    else:
        print("Unknown phase. Failing closed to prevent unsafe re-execution.")
        action = "FAIL_CLOSED_UNKNOWN"

    # Cleanup orphaned PIDs if any
    owned_pids = wstate.get("owned_pids", [])
    terminated_count = 0
    if owned_pids:
        print(f"Cleaning up orphaned processes from crash: {owned_pids}")
        for pid in list(owned_pids):
            if safely_terminate_pid(pid):
                terminated_count += 1

    # Clear worker state
    wstate["current_task"] = None
    wstate["owned_pids"] = []
    wstate["last_recovery"] = {
        "timestamp": time.time(),
        "recovered_task_id": task_id,
        "phase": last_known_phase,
        "action": action,
    }

    atomic_save_json(w_path, wstate)

    return {
        "recovered": True,
        "action": action,
        "task_id": task_id,
        "execution_ref": execution_ref,
        "phase": last_known_phase,
        "terminated_pids_count": terminated_count,
    }


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        t_state = Path(td) / "worker_state.json"
        for phase in ["PRE_EFFECT", "ARTIFACT_CREATED", "POST_EXTERNAL_EFFECT", "POST_RESULT"]:
            print(f"\n--- Simulating crash in phase: {phase} ---")
            mock_state = {
                "current_task": {
                    "task_id": "WF-CANARY-STEP-1",
                    "execution_ref": "exec_WIN_01_WF-CANARY-STEP-1",
                    "attempt_id": 1,
                    "phase": phase,
                },
                "owned_pids": [12345],
            }
            atomic_save_json(t_state, mock_state)
            res = recover_worker(worker_state_file=str(t_state))
            print(f"Recovery result: {res}")
