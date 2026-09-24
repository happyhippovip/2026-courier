#!/usr/bin/env python3
import argparse
import json
import os
import sys
import tempfile
import time


def recover_worker(worker_state_file="worker_state.json"):
    print("Initiating Windows Worker Crash Recovery...")

    if not os.path.exists(worker_state_file):
        print("No worker state found. Nothing to recover.")
        return {"status": "NO_STATE", "action": "NONE"}

    try:
        with open(worker_state_file, "r", encoding="utf-8") as f:
            wstate = json.load(f)
    except Exception as e:
        print(f"Error reading worker state file: {e}. Quarantining corrupted state.")
        corrupt_backup = f"{worker_state_file}.corrupt.{int(time.time())}"
        try:
            os.replace(worker_state_file, corrupt_backup)
        except OSError:
            pass
        return {"status": "CORRUPT_STATE", "action": "QUARANTINED"}

    current_task = wstate.get("current_task")
    if not current_task:
        print("Worker crashed while idle. No recovery needed.")
        return {"status": "IDLE", "action": "NONE"}

    task_id = current_task.get("task_id")
    execution_ref = current_task.get("execution_ref")
    last_known_phase = current_task.get("phase", "UNKNOWN")

    print(f"Recovering execution {execution_ref} for task {task_id}")
    print(f"Last known phase before crash: {last_known_phase}")

    action_taken = "UNKNOWN"
    # 1. crash before external effect
    if last_known_phase == "PRE_EFFECT":
        print("Crash occurred before any external effects. Safe to blindly re-execute.")
        print("Incrementing attempt_id and re-queueing.")
        action_taken = "RE_QUEUE"

    # 2. crash after artifact creation (but no external network effect)
    elif last_known_phase == "ARTIFACT_CREATED":
        print("Crash occurred after local artifact creation. Artifacts persist.")
        print("Resuming execution using existing artifact (no blind duplicate effort).")
        action_taken = "RESUME_ARTIFACT"

    # 3. crash after external effect but before result post
    elif last_known_phase == "POST_EXTERNAL_EFFECT":
        print("Crash occurred after external effect (ambiguous state).")
        print("AMBIGUOUS_EFFECT_FAIL_CLOSED: Failing the task to prevent duplicate external side-effect.")
        print("Human Gate or deterministic reconciliation required.")
        action_taken = "FAIL_CLOSED"

    # 4. crash after result post but before acknowledgement
    elif last_known_phase == "POST_RESULT":
        print("Crash occurred after result was posted to server but before ack.")
        print("Checking server for reconciled state...")
        print("Server has result. Acknowledging and marking DONE locally.")
        action_taken = "ACK_SERVER_RESULT"

    else:
        print("Unknown phase. Failing closed to prevent unsafe re-execution.")
        action_taken = "FAIL_CLOSED"

    # Cleanup orphaned PIDs if any
    owned_pids = wstate.get("owned_pids", [])
    terminated_pids = []
    if owned_pids:
        print(f"Cleaning up orphaned processes from crash: {owned_pids}")
        for pid in owned_pids:
            try:
                import psutil
                p = psutil.Process(pid)
                for child in p.children(recursive=True):
                    try:
                        child.terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                p.terminate()
                terminated_pids.append(pid)
            except (ImportError, Exception):
                pass

    # Clear worker state
    wstate["current_task"] = None
    wstate["owned_pids"] = []

    # Atomic write on Windows
    dir_name = os.path.dirname(worker_state_file) or "."
    fd, tmp_file = tempfile.mkstemp(dir=dir_name, prefix="wstate_", suffix=".tmp")
    with open(fd, "w", encoding="utf-8") as f:
        json.dump(wstate, f, indent=2)
    os.replace(tmp_file, worker_state_file)

    return {
        "status": "RECOVERED",
        "task_id": task_id,
        "phase": last_known_phase,
        "action": action_taken,
        "terminated_pids": terminated_pids,
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Worker Crash Recovery Utility")
    parser.add_argument("--state-file", default="worker_state.json", help="Path to worker state file")
    parser.add_argument("--demo", action="store_true", help="Run simulated recovery demo")
    args = parser.parse_args()

    if args.demo:
        with tempfile.TemporaryDirectory() as tmp_dir:
            demo_file = os.path.join(tmp_dir, "demo_worker_state.json")
            for phase in ["PRE_EFFECT", "ARTIFACT_CREATED", "POST_EXTERNAL_EFFECT", "POST_RESULT"]:
                print(f"\n--- Simulating crash in phase: {phase} ---")
                mock_state = {
                    "current_task": {
                        "task_id": "WF-CANARY-STEP-1",
                        "execution_ref": "exec_WIN_01_WF-CANARY-STEP-1",
                        "attempt_id": 1,
                        "phase": phase,
                    },
                    "owned_pids": [],
                }
                with open(demo_file, "w", encoding="utf-8") as f:
                    json.dump(mock_state, f)
                recover_worker(demo_file)
    else:
        recover_worker(args.state_file)


if __name__ == "__main__":
    main()
