#!/usr/bin/env python3
"""Run exactly one Chief Relay cycle: Pull -> Discover -> Build Worker Job -> Consume -> Validate -> Commit -> Push."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(f"RELAY_CYCLE_ERROR: {message}")


def is_command_pending(cmd_file: Path, processed_dir: Path) -> bool:
    try:
        data = json.loads(cmd_file.read_text(encoding="utf-8"))
    except Exception:
        return False

    if data.get("schema_version") != "2.0":
        return False
    if data.get("type") != "COMMAND" or data.get("status") != "NEW":
        return False
    if data.get("source") != "chief" or data.get("destination") != "antigravity":
        return False

    msg_id = data.get("message_id")
    if not msg_id:
        return False

    # Check if a result already exists in processed_dir for this message_id or task_id
    if processed_dir.exists():
        for proc_file in processed_dir.glob("*.json"):
            try:
                proc_data = json.loads(proc_file.read_text(encoding="utf-8"))
                if proc_data.get("parent_id") == msg_id or proc_data.get("message_id") == msg_id:
                    return False
            except Exception:
                continue

    return True


def discover_pending_command(incoming_dir: Path, processed_dir: Path) -> Path | None:
    if not incoming_dir.exists():
        return None

    candidates = sorted(incoming_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    for candidate in candidates:
        if is_command_pending(candidate, processed_dir):
            return candidate
    return None


def run_cycle(
    repo_dir: Path,
    incoming_dir: Path,
    processed_dir: Path,
    dispatch_dir: Path,
    pull: bool = False,
    push: bool = False,
) -> dict:
    # 1. Optional Pull
    if pull:
        res = subprocess.run(["git", "-C", str(repo_dir), "pull", "--ff-only", "origin", "main"], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"PULL_WARNING: {res.stderr.strip()}", file=sys.stderr)

    # 2. Discover exactly one pending command
    pending_cmd = discover_pending_command(incoming_dir, processed_dir)
    if not pending_cmd:
        return {
            "status": "IDLE",
            "message": "No pending Chief COMMAND found in incoming directory",
            "command_processed": None,
            "worker_job_path": None,
            "result_path": None,
        }

    cmd_data = json.loads(pending_cmd.read_text(encoding="utf-8"))
    task_id = cmd_data["task_id"]

    # 3a. Build Worker Job Dispatch Contract
    build_job_script = repo_dir / "scripts/build_antigravity_worker_job.py"
    build_res = subprocess.run(
        [
            sys.executable,
            str(build_job_script),
            "--command",
            str(pending_cmd),
            "--output-dir",
            str(dispatch_dir),
        ],
        capture_output=True,
        text=True,
    )
    if build_res.returncode != 0:
        fail(f"Worker job builder failed: {build_res.stderr.strip()}")

    worker_job_file = dispatch_dir / f"{task_id}-worker-job.json"
    if not worker_job_file.exists():
        fail(f"Worker job file was not created: {worker_job_file}")

    # 3b. Consume command
    consume_script = repo_dir / "scripts/consume_chief_command.py"
    res = subprocess.run(
        [
            sys.executable,
            str(consume_script),
            "--command",
            str(pending_cmd),
            "--incoming-dir",
            str(incoming_dir),
            "--processed-dir",
            str(processed_dir),
        ],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        fail(f"Consumer failed: {res.stderr.strip()}")

    # Find the newly generated result file
    result_file = processed_dir / f"{task_id}-result.json"
    if not result_file.exists():
        fail(f"Result file was not created: {result_file}")

    # 4. Validate generated result
    val_script = repo_dir / "scripts/validate_chief_relay.py"
    val_res = subprocess.run(
        [
            sys.executable,
            str(val_script),
            "--file",
            str(result_file),
            "--incoming-dir",
            str(incoming_dir),
            "--processed-dir",
            str(processed_dir),
        ],
        capture_output=True,
        text=True,
    )
    if val_res.returncode != 0:
        fail(f"Result validation failed: {val_res.stderr.strip()}")

    # 5. Optional Git Commit & Push
    commit_sha = None
    if push:
        subprocess.run(["git", "-C", str(repo_dir), "add", "-f", str(worker_job_file), str(result_file)], check=True)
        commit_msg = f"Publish Antigravity worker job and result for {task_id} ({cmd_data['message_id']})"
        subprocess.run(["git", "-C", str(repo_dir), "commit", "-m", commit_msg], check=True)
        push_res = subprocess.run(["git", "-C", str(repo_dir), "push", "origin", "main"], capture_output=True, text=True)
        if push_res.returncode != 0:
            fail(f"Git push failed: {push_res.stderr.strip()}")
        rev_res = subprocess.run(["git", "-C", str(repo_dir), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        commit_sha = rev_res.stdout.strip()

    return {
        "status": "COMPLETED",
        "command_processed": pending_cmd.as_posix(),
        "task_id": task_id,
        "message_id": cmd_data["message_id"],
        "worker_job_path": worker_job_file.as_posix(),
        "result_path": result_file.as_posix(),
        "commit_sha": commit_sha,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Chief Relay cycle (max_iterations=1)")
    parser.add_argument("--repo-dir", default=".", help="Repository root directory")
    parser.add_argument("--incoming-dir", default="events/incoming", help="Incoming events directory")
    parser.add_argument("--processed-dir", default="events/processed", help="Processed events directory")
    parser.add_argument("--dispatch-dir", default="events/dispatch", help="Dispatch worker jobs directory")
    parser.add_argument("--pull", action="store_true", help="Pull latest main before processing")
    parser.add_argument("--push", action="store_true", help="Commit and push result after processing")
    args = parser.parse_args()

    repo_dir = Path(args.repo_dir).resolve()
    incoming_dir = (repo_dir / args.incoming_dir).resolve()
    processed_dir = (repo_dir / args.processed_dir).resolve()
    dispatch_dir = (repo_dir / args.dispatch_dir).resolve()

    result = run_cycle(
        repo_dir=repo_dir,
        incoming_dir=incoming_dir,
        processed_dir=processed_dir,
        dispatch_dir=dispatch_dir,
        pull=args.pull,
        push=args.push,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
