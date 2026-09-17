#!/usr/bin/env python3
"""Run Chief Relay Cycle with End-to-End Autonomous Memory Policy (086 -> 087 -> 088 -> 089).

Full Lifecycle:
1. Optional Pull
2. Discover pending Chief COMMAND
3. Resolve Memory Context & Build Worker Job (085)
4. Validate Worker Job against JSON Schema
5. Execute / Consume Command -> Produce RESULT
6. Validate Result envelope
7. Generate Memory Update Proposal (086)
8. Evaluate Autonomous Chief Policy (088):
   - AUTO_APPROVE -> Generate 087 Approval -> Execute 087 Memory Write Handler (or Dry-Run)
   - HUMAN_REVIEW -> Gracefully queue at Human Gate (Zero writes)
   - BLOCKED      -> Gracefully block on policy violation (Zero writes)
9. Optional Commit & Push of relay event records
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

DEFAULT_MEMORY_REPO = Path("/Users/user/Downloads/2026-project-memory")


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
    proposals_dir: Path = Path("events/proposals"),
    approvals_dir: Path = Path("events/approvals"),
    decisions_dir: Path = Path("events/chief-decisions"),
    memory_repo: Path = DEFAULT_MEMORY_REPO,
    enable_auto_memory: bool = True,
    memory_dry_run: bool = False,
    pull: bool = False,
    push: bool = False,
) -> dict:
    # 1. Optional Pull
    if pull:
        res = subprocess.run(["git", "-C", str(repo_dir, timeout=120), "pull", "--ff-only", "origin", "main"], capture_output=True, text=True)
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
            "memory_cycle": None,
        }

    cmd_data = json.loads(pending_cmd.read_text(encoding="utf-8"))
    task_id = cmd_data["task_id"]

    # 3a. Build Worker Job Dispatch Contract with Memory Resolution (085)
    build_job_script = repo_dir / "scripts/build_antigravity_worker_job.py"
    build_cmd = [
        sys.executable,
        str(build_job_script),
        "--command",
        str(pending_cmd),
        "--output-dir",
        str(dispatch_dir),
    ]
    if memory_repo and memory_repo.exists():
        build_cmd.extend(["--memory-repo", str(memory_repo)])

    build_res = subprocess.run(build_cmd, capture_output=True, text=True, timeout=120)
    if build_res.returncode != 0:
        fail(f"Worker job builder failed: {build_res.stderr.strip()}")

    worker_job_file = dispatch_dir / f"{task_id}-worker-job.json"
    if not worker_job_file.exists():
        fail(f"Worker job file was not created: {worker_job_file}")

    # 3b. Validate Worker Job against JSON Schema
    val_job_res = subprocess.run(
        [
            sys.executable,
            str(build_job_script, timeout=120),
            "--validate-job",
            str(worker_job_file),
            "--schema",
            str(repo_dir / "schemas/antigravity_worker_job.schema.json"),
        ],
        capture_output=True,
        text=True,
    )
    if val_job_res.returncode != 0:
        fail(f"Worker job JSON Schema validation failed: {val_job_res.stderr.strip()}")

    # 3c. Consume command -> Generate RESULT
    consume_script = repo_dir / "scripts/consume_chief_command.py"
    res = subprocess.run(
        [
            sys.executable,
            str(consume_script, timeout=120),
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

    result_file = processed_dir / f"{task_id}-result.json"
    if not result_file.exists():
        fail(f"Result file was not created: {result_file}")

    # 4. Validate generated result
    val_script = repo_dir / "scripts/validate_chief_relay.py"
    val_res = subprocess.run(
        [
            sys.executable,
            str(val_script, timeout=120),
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

    # 5. Autonomous Memory Pipeline (086 -> 088 -> 087)
    memory_cycle_summary = None
    if enable_auto_memory and memory_repo and memory_repo.exists():
        # 5a. Build Memory Update Proposal (086)
        prop_builder = repo_dir / "scripts/build_memory_update_proposal.py"
        prop_cmd = [
            sys.executable,
            str(prop_builder),
            "--result",
            str(result_file),
            "--memory-repo",
            str(memory_repo),
            "--output-dir",
            str(proposals_dir),
        ]
        prop_res = subprocess.run(prop_cmd, capture_output=True, text=True, timeout=120)
        if prop_res.returncode != 0:
            fail(f"Memory proposal builder failed: {prop_res.stderr.strip()}")

        proposal_file = proposals_dir / f"{task_id}-memory-proposal.json"
        if not proposal_file.exists():
            fail(f"Proposal file was not created: {proposal_file}")

        # 5b. Evaluate Autonomous Chief Policy (088)
        eval_script = repo_dir / "scripts/evaluate_memory_proposal_for_auto_approval.py"
        eval_cmd = [
            sys.executable,
            str(eval_script),
            "--proposal",
            str(proposal_file),
            "--memory-repo",
            str(memory_repo),
            "--output-decisions",
            str(decisions_dir),
            "--output-approvals",
            str(approvals_dir),
        ]
        eval_res = subprocess.run(eval_cmd, capture_output=True, text=True, timeout=120)
        if eval_res.returncode != 0:
            fail(f"Autonomous Chief Policy evaluation failed: {eval_res.stderr.strip()}")

        decision_file = decisions_dir / f"{task_id}-chief-decision.json"
        if not decision_file.exists():
            fail(f"Decision file was not created: {decision_file}")

        decision_data = json.loads(decision_file.read_text(encoding="utf-8"))
        decision_status = decision_data["decision"]

        write_result = None
        if decision_status == "AUTO_APPROVE":
            approval_file = approvals_dir / f"{task_id}-auto-approval.json"
            if not approval_file.exists():
                fail(f"Auto-approval file was not created: {approval_file}")

            # 5c. Apply Memory Write Handler (087)
            apply_script = repo_dir / "scripts/apply_memory_update_proposal.py"
            apply_cmd = [
                sys.executable,
                str(apply_script),
                "--proposal",
                str(proposal_file),
                "--approval",
                str(approval_file),
                "--memory-repo",
                str(memory_repo),
            ]
            if memory_dry_run:
                apply_cmd.append("--dry-run")

            apply_res = subprocess.run(apply_cmd, capture_output=True, text=True, timeout=120)
            if apply_res.returncode != 0:
                fail(f"Memory write handler failed: {apply_res.stderr.strip()}")
            write_result = json.loads(apply_res.stdout.strip())

        memory_cycle_summary = {
            "proposal_path": proposal_file.as_posix(),
            "decision": decision_status,
            "reason_codes": decision_data["reason_codes"],
            "decision_path": decision_file.as_posix(),
            "approval_path": (approvals_dir / f"{task_id}-auto-approval.json").as_posix() if decision_status == "AUTO_APPROVE" else None,
            "write_result": write_result,
        }

    # 6. Optional Git Commit & Push
    commit_sha = None
    if push:
        subprocess.run(["git", "-C", str(repo_dir, timeout=120), "add", "-f", str(worker_job_file), str(result_file)], check=True)
        commit_msg = f"Publish Antigravity worker job and result for {task_id} ({cmd_data['message_id']})"
        subprocess.run(["git", "-C", str(repo_dir, timeout=120), "commit", "-m", commit_msg], check=True)
        push_res = subprocess.run(["git", "-C", str(repo_dir, timeout=120), "push", "origin", "main"], capture_output=True, text=True)
        if push_res.returncode != 0:
            fail(f"Git push failed: {push_res.stderr.strip()}")
        rev_res = subprocess.run(["git", "-C", str(repo_dir, timeout=120), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        commit_sha = rev_res.stdout.strip()

    return {
        "status": "COMPLETED",
        "command_processed": pending_cmd.as_posix(),
        "task_id": task_id,
        "message_id": cmd_data["message_id"],
        "worker_job_path": worker_job_file.as_posix(),
        "result_path": result_file.as_posix(),
        "memory_cycle": memory_cycle_summary,
        "commit_sha": commit_sha,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Chief Relay cycle with Autonomous Memory Policy (max_iterations=1)")
    parser.add_argument("--repo-dir", default=".", help="Repository root directory")
    parser.add_argument("--incoming-dir", default="events/incoming", help="Incoming events directory")
    parser.add_argument("--processed-dir", default="events/processed", help="Processed events directory")
    parser.add_argument("--dispatch-dir", default="events/dispatch", help="Dispatch worker jobs directory")
    parser.add_argument("--proposals-dir", default="events/proposals", help="Memory proposals directory")
    parser.add_argument("--approvals-dir", default="events/approvals", help="Approvals directory")
    parser.add_argument("--decisions-dir", default="events/chief-decisions", help="Chief decisions directory")
    parser.add_argument("--memory-repo", default=str(DEFAULT_MEMORY_REPO), help="Path to canonical 2026-project-memory")
    parser.add_argument("--disable-auto-memory", action="store_true", help="Disable autonomous memory cycle")
    parser.add_argument("--memory-dry-run", action="store_true", help="Execute memory write in dry-run mode")
    parser.add_argument("--pull", action="store_true", help="Pull latest main before processing")
    parser.add_argument("--push", action="store_true", help="Commit and push result after processing")
    args = parser.parse_args()

    repo_dir = Path(args.repo_dir).resolve()
    incoming_dir = (repo_dir / args.incoming_dir).resolve()
    processed_dir = (repo_dir / args.processed_dir).resolve()
    dispatch_dir = (repo_dir / args.dispatch_dir).resolve()
    proposals_dir = (repo_dir / args.proposals_dir).resolve()
    approvals_dir = (repo_dir / args.approvals_dir).resolve()
    decisions_dir = (repo_dir / args.decisions_dir).resolve()
    memory_repo = Path(args.memory_repo).resolve() if args.memory_repo else None

    result = run_cycle(
        repo_dir=repo_dir,
        incoming_dir=incoming_dir,
        processed_dir=processed_dir,
        dispatch_dir=dispatch_dir,
        proposals_dir=proposals_dir,
        approvals_dir=approvals_dir,
        decisions_dir=decisions_dir,
        memory_repo=memory_repo,
        enable_auto_memory=not args.disable_auto_memory,
        memory_dry_run=args.memory_dry_run,
        pull=args.pull,
        push=args.push,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
