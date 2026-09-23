#!/usr/bin/env python3
import datetime
import json
import logging
import os
from pathlib import Path
import platform
import subprocess
import sys
import zipfile

try:
    from scripts.orphan_task_reaper import (
        REPO_ROOT,
        get_canonical_state_path,
    )
except ImportError:
    from orphan_task_reaper import (
        REPO_ROOT,
        get_canonical_state_path,
    )

logger = logging.getLogger("support_bundle")


def get_system_health() -> dict:
    health = {
        "os": os.name,
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "timestamp_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "disk_free_gb": "N/A",
    }
    try:
        import shutil
        total, used, free = shutil.disk_usage(".")
        health["disk_free_gb"] = round(free / (1024**3), 2)
    except Exception:
        if hasattr(os, "statvfs"):
            try:
                st = os.statvfs(".")
                health["disk_free_gb"] = round((st.f_bavail * st.f_frsize) / (1024**3), 2)
            except Exception:
                pass
    return health


def generate_redacted_queue_summary(state_path: Path) -> dict:
    if not state_path.exists():
        return {"status": "state_file_not_found"}

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)

        if not isinstance(state, dict):
            return {"status": "malformed_root", "error": "Root JSON is not a dictionary"}

        goals = state.get("goals", {})
        tasks = state.get("tasks", {})

        status_counts = {}
        total_workflow_tasks = 0
        for goal_id, goal_data in goals.items():
            if isinstance(goal_data, dict):
                for t in goal_data.get("workflow_plan", []):
                    if isinstance(t, dict):
                        total_workflow_tasks += 1
                        st = t.get("status", "UNKNOWN")
                        status_counts[st] = status_counts.get(st, 0) + 1

        summary = {
            "status": "available",
            "schema_version": state.get("schema_version", "unknown"),
            "total_goals": len(goals),
            "total_top_level_tasks": len(tasks),
            "total_workflow_tasks": total_workflow_tasks,
            "status_counts": status_counts,
        }
        return summary
    except Exception as e:
        return {"status": "unparseable", "error": str(e)}


def create_support_bundle(state_file=None, output_dir=None) -> Path:
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(output_dir).resolve() if output_dir else REPO_ROOT
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = out_dir / f"support_bundle_{timestamp}.zip"

    canonical_state = get_canonical_state_path(state_file)

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Health Info (sanitized)
        health_info = get_system_health()
        zf.writestr("health.json", json.dumps(health_info, indent=2))

        # 2. Redacted State (only queue metrics, zero secrets or execution payloads)
        queue_summary = generate_redacted_queue_summary(canonical_state)
        zf.writestr("queue_summary.json", json.dumps(queue_summary, indent=2))

        # 3. Version Info (bounded timeout git check)
        git_hash = "unknown"
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=str(REPO_ROOT),
            )
            if res.returncode == 0:
                git_hash = res.stdout.strip()
        except Exception:
            pass
        zf.writestr("version.txt", f"git_hash: {git_hash}\n")

    print(f"Support bundle created: {bundle_path}")
    return bundle_path


if __name__ == "__main__":
    bundle = create_support_bundle()
    print(f"Support bundle ready at: {bundle}")
