#!/usr/bin/env python3
"""Courier Support Bundle Generator.

Gathers non-sensitive diagnostic telemetry, queue summaries, version information,
and system health for troubleshooting, strictly redacting secrets and private data.
"""

import argparse
import datetime
import json
import os
import platform
import shutil
import subprocess
import sys
import zipfile


def get_system_health(target_path="."):
    """Retrieve system health metrics safely and cross-platform (Windows & POSIX)."""
    health = {
        "os": os.name,
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "disk_free_gb": "N/A",
        "disk_total_gb": "N/A",
    }
    try:
        usage = shutil.disk_usage(target_path)
        health["disk_free_gb"] = round(usage.free / (1024**3), 2)
        health["disk_total_gb"] = round(usage.total / (1024**3), 2)
    except Exception as e:
        health["disk_error"] = str(e)
    return health


def create_support_bundle(repo_dir=None, output_dir=None):
    """Create a zipped support bundle with sanitized diagnostics."""
    if repo_dir is None:
        repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    else:
        repo_dir = os.path.abspath(repo_dir)

    if output_dir is None:
        output_dir = repo_dir
    else:
        output_dir = os.path.abspath(output_dir)

    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    bundle_name = f"support_bundle_{timestamp}.zip"
    bundle_path = os.path.join(output_dir, bundle_name)

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. System health
        health_info = get_system_health(repo_dir)
        zf.writestr("health.json", json.dumps(health_info, indent=2))

        # 2. Redacted state summary (queue sizes and counts only; NO keys, tokens, or CoT)
        state_candidates = [
            os.path.join(repo_dir, "central_state.json"),
            os.path.join(repo_dir, "courier_state.json"),
        ]
        found_state = False
        for sfile in state_candidates:
            if os.path.exists(sfile):
                found_state = True
                try:
                    with open(sfile, "r", encoding="utf-8") as f:
                        state = json.load(f)
                    redacted_state = {
                        "source_file": os.path.basename(sfile),
                        "queue_summary": {
                            "total_goals": len(state.get("goals", {})) if isinstance(state.get("goals"), (dict, list)) else 0,
                            "total_tasks": len(state.get("tasks", {})) if isinstance(state.get("tasks"), (dict, list)) else 0,
                            "status": state.get("status", "UNKNOWN"),
                        },
                    }
                    zf.writestr("queue_summary.json", json.dumps(redacted_state, indent=2))
                    break
                except Exception as e:
                    zf.writestr("queue_summary.json", json.dumps({"error": str(e)}, indent=2))

        if not found_state:
            zf.writestr("queue_summary.json", json.dumps({"info": "No central state found"}, indent=2))

        # 3. Version info
        version_txt = os.path.join(repo_dir, "version.txt")
        if os.path.exists(version_txt):
            try:
                with open(version_txt, "r", encoding="utf-8") as f:
                    zf.writestr("version.txt", f.read())
            except Exception:
                pass
        else:
            try:
                git_hash = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=repo_dir, stderr=subprocess.DEVNULL
                ).decode("utf-8").strip()
                zf.writestr("version.txt", f"git_hash: {git_hash}\n")
            except Exception:
                zf.writestr("version.txt", "version: unknown\n")

    print(f"Support bundle created: {bundle_path}")
    return bundle_path


def main():
    parser = argparse.ArgumentParser(description="Courier Support Bundle Generator")
    parser.add_argument("--repo-dir", help="Path to repository root")
    parser.add_argument("--output-dir", help="Directory where support bundle is saved")
    args = parser.parse_args()

    create_support_bundle(repo_dir=args.repo_dir, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
