#!/usr/bin/env python3
"""Gemini Worker Adapter for Antigravity.

Dispatches bounded tasks to the local Antigravity CLI (agy) and reconciles results:
- Autonomous non-interactive execution with --dangerously-skip-permissions
- Safe JSON output parsing with markdown codeblock stripping
- Strict fail-closed semantics on malformed or non-JSON outputs
- Atomic central state reconciliation
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid


def run_worker(task_path, negative_test=False, output_dir=None, state_file=None):
    with open(task_path, "r", encoding="utf-8") as f:
        task = json.load(f)

    task_id = task["task_id"]
    if negative_test:
        prompt = f"Task: {task_id}\nInstruction: Output garbage text, DO NOT output JSON."
    else:
        instruction = task.get("instruction", "Execute task and return status.")
        prompt = f"Task: {task_id}\nInstruction: {instruction}\nReturn ONLY a JSON object with status."

    print(f"Dispatching task {task_id} to Antigravity Gemini Worker...")

    agy_bin = shutil.which("agy") or shutil.which("agy.cmd") or shutil.which("agy.exe") or "agy"
    cmd = [
        agy_bin,
        "-p", prompt,
        "--disable-slash-commands",
        "--dangerously-skip-permissions",
    ]

    dispatch_ref = str(uuid.uuid4())

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        pid = process.pid
        stdout, stderr = process.communicate(timeout=60)
    except FileNotFoundError:
        # agy CLI not found on machine
        pid = 0
        stdout = ""
        stderr = f"Executable '{agy_bin}' not found on PATH."
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        pid = process.pid

    out = stdout.strip()

    # Parse JSON safely
    parsed = False
    if "```json" in out:
        out_clean = out.split("```json")[1].split("```")[0].strip()
    elif "```" in out:
        out_clean = out.split("```")[1].split("```")[0].strip()
    else:
        out_clean = out

    try:
        res_json = json.loads(out_clean)
        parsed = True
    except Exception:
        res_json = {
            "status": "FAILED",
            "reason": "INVALID_RESULT",
            "raw_diagnostic": out,
            "stderr": stderr,
        }

    res_json["pid"] = pid
    res_json["dispatch_ref"] = dispatch_ref

    # If the output didn't contain JSON, we must fail closed (status should not be SUCCESS)
    if not parsed and res_json.get("status") == "SUCCESS":
        res_json["status"] = "FAILED"
        res_json["reason"] = "FORCED_FAIL_CLOSED"

    out_folder = output_dir or os.path.dirname(task_path) or "."
    result_ref = os.path.join(out_folder, f"gemini_result_{task_id}.json")
    with open(result_ref, "w", encoding="utf-8") as f:
        json.dump(res_json, f, indent=2)

    consume(res_json, task_id, result_ref, state_file=state_file)
    return pid, dispatch_ref, result_ref


def consume(res_json, task_id, result_ref, state_file=None):
    if state_file is None:
        state_file = "central_state.json"

    try:
        if os.path.exists(state_file):
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
        else:
            state = {"tasks": {}}
    except Exception:
        state = {"tasks": {}}

    status = res_json.get("status", "FAILED")

    state.setdefault("tasks", {})[task_id] = {
        "task_id": task_id,
        "worker_id": "gemini-local-agy",
        "platform": "antigravity",
        "dispatch_ref": res_json.get("dispatch_ref"),
        "pid": res_json.get("pid"),
        "state": "RECONCILED",
        "reconciled_status": status,
        "result_ref": result_ref,
        "last_transition": "AUTOMATIC_CONSUMPTION",
        "next_explicit_transition": "HUMAN_REVIEW_REQUIRED" if status == "SUCCESS" else "STOP_FAILED",
        "real_wall": "HUMAN_REVIEW_REQUIRED" if status == "SUCCESS" else "DIAGNOSTIC_REQUIRED",
    }

    dir_name = os.path.dirname(state_file) or "."
    fd, tmp_file = tempfile.mkstemp(dir=dir_name, prefix="state_", suffix=".tmp")
    with open(fd, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp_file, state_file)


def main():
    parser = argparse.ArgumentParser(description="Gemini Worker Adapter")
    parser.add_argument("task_file", help="Path to Task JSON file")
    parser.add_argument("--negative", action="store_true", help="Run negative test expecting garbage response")
    parser.add_argument("--state-file", help="Path to central state file")
    args = parser.parse_args()

    run_worker(args.task_file, negative_test=args.negative, state_file=args.state_file)


if __name__ == "__main__":
    main()
