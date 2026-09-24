#!/usr/bin/env python3
"""Customer Data Export Utility.

Exports customer-owned durable data (goals, results, artifact refs, timestamps)
without exporting secrets, chain-of-thought, or internal prompt engineering.
"""

import argparse
import datetime
import json
import os
import sys
import tempfile
from pathlib import Path


def export_customer_data(
    export_path: str = "customer_export.json",
    state_file: str | None = None,
    repo_dir: str | None = None,
    dry_run: bool = False,
    quiet: bool = False,
) -> dict | None:
    """Exports customer-owned durable data with atomic persistence."""
    if state_file is None:
        if repo_dir:
            state_file = os.path.join(repo_dir, "central_state.json")
        else:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            local_state = os.path.join(base_dir, "central_state.json")
            state_file = local_state if os.path.exists(local_state) else "central_state.json"

    if not os.path.exists(state_file):
        if not quiet:
            print(f"No state file found at {state_file}.")
        return None

    try:
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        if not quiet:
            print(f"Failed to decode state file: {e}")
        return None

    export_data = {
        "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "goals": [],
        "tasks": [],
    }

    # Extract goals (if any in state)
    if "goals" in state:
        for goal_id, goal_data in state["goals"].items():
            export_data["goals"].append({
                "goal_id": goal_id,
                "description": goal_data.get("description", ""),
                "status": goal_data.get("status", "UNKNOWN"),
                "created_at": goal_data.get("created_at", ""),
                "completed_at": goal_data.get("completed_at", ""),
            })

    # Extract tasks
    if "tasks" in state:
        for task_id, task_data in state["tasks"].items():
            # Exclude chain of thought, full logs, secrets
            export_data["tasks"].append({
                "task_id": task_id,
                "type": task_data.get("type", "UNKNOWN"),
                "status": task_data.get("status", "UNKNOWN"),
                "created_at": task_data.get("created_at", ""),
                "completed_at": task_data.get("completed_at", ""),
                "artifacts": task_data.get("artifacts", []),
                "error_summary": task_data.get("error_summary", ""),
            })

    if dry_run:
        if not quiet:
            print(f"[DRY-RUN] Prepared export with {len(export_data['goals'])} goals and {len(export_data['tasks'])} tasks.")
        return export_data

    out_file = Path(export_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_file = tempfile.mkstemp(dir=out_file.parent, prefix="export_", suffix=".tmp")
    with open(fd, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2)
    os.replace(tmp_file, out_file)

    if not quiet:
        print(f"Customer data successfully exported to {out_file}")

    return export_data


def main():
    parser = argparse.ArgumentParser(description="Export Courier Customer Durable Data")
    parser.add_argument("export_path", nargs="?", default="customer_export.json", help="Destination path for export file")
    parser.add_argument("--state-file", help="Path to central_state.json")
    parser.add_argument("--repo-dir", help="Repository root path")
    parser.add_argument("--dry-run", action="store_true", help="Prepare export without writing to disk")
    parser.add_argument("--json", action="store_true", help="Print export JSON to stdout")
    args = parser.parse_args()

    data = export_customer_data(
        export_path=args.export_path,
        state_file=args.state_file,
        repo_dir=args.repo_dir,
        dry_run=args.dry_run,
        quiet=args.json,
    )
    if args.json and data is not None:
        print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
