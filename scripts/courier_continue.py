#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path
import sys
import os

# Ensure scripts module is in PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

try:
    from scripts.resource_policy import (
        ChiefContextPackageBuilder,
        FileManifestTracker,
        TaskDedupeEngine
    )
    from scripts.agent_handoff_ledger import freshness, load_bundle
except ImportError as e:
    print(f"Failed to import required primitives: {e}")
    sys.exit(1)

def get_git_info():
    if "MOCK_SHA" in os.environ and "MOCK_BRANCH" in os.environ:
        return os.environ["MOCK_BRANCH"], os.environ["MOCK_SHA"]
    try:
        branch = subprocess.check_output(["git", "branch", "--show-current"]).decode().strip()
        # Separate runtime/evidence SHA from Ledger commit identity
        # The evidence SHA is the latest commit that touched the code (ignoring the ledger itself)
        sha = subprocess.check_output([
            "git", "log", "-1", "--format=%H", "--", ".", ":(exclude)agent_handoff_ledger.json"
        ]).decode().strip()
        
        # Fallback to HEAD if it's a completely fresh repo
        if not sha:
            sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
            
        return branch, sha
    except subprocess.CalledProcessError:
        return "UNKNOWN", "UNKNOWN"

def check_freshness(ledger_path: Path, branch: str, sha: str):
    bundle = load_bundle(ledger_path)
    result = freshness(bundle, branch, sha, "NO_FURTHER_ACTION", [])
    if result["FRESHNESS"] == "STALE":
        print("ERROR: Ledger is stale. Fail closed.")
        print(json.dumps(result, indent=2))
        sys.exit(3)
    return bundle

def compute_frontier(record: dict):
    unproven = record.get("UNPROVEN_EDGES", [])
    first_blocker = record.get("FIRST_CAUSAL_BLOCKER", "")
    
    tasks = []
    for edge in unproven:
        tasks.append({
            "id": f"TASK-{hash(edge)}",
            "instruction": f"Prove edge: {edge}",
            "scope": "independent" if "independent" in edge.lower() else "dependent"
        })
        
    return tasks

def main():
    repo_dir = Path(__file__).parent.parent.resolve()
    ledger_path_str = os.environ.get("MOCK_LEDGER")
    if ledger_path_str:
        ledger_path = Path(ledger_path_str)
    else:
        ledger_path = repo_dir / "agent_handoff_ledger.json"
    
    if not ledger_path.exists():
        print("ERROR: agent_handoff_ledger.json not found.")
        sys.exit(1)
        
    branch, sha = get_git_info()
    bundle = check_freshness(ledger_path, branch, sha)
    record = bundle["record"]
    
    print(f"Goal: {record.get('GOAL')}")
    print(f"Branch/SHA: {branch} / {sha}")
    print(f"Active Writers: {record.get('ACTIVE_WRITERS', [])}")
    
    tasks = compute_frontier(record)
    
    safe_executable_tasks = [t for t in tasks if t["scope"] == "independent"]
    
    first_blocker = record.get("FIRST_CAUSAL_BLOCKER", "")
    is_blocked_by_human = "HUMAN_REQUIRED" in first_blocker or "MONEY_REQUIRED" in first_blocker
    
    if is_blocked_by_human and not safe_executable_tasks:
        print(f"GLOBAL STOP: CLEAN_IDLE. No safe, unowned, independent executable tasks exist.")
        print(f"Blocker: {first_blocker}")
        sys.exit(0)
        
    if not tasks and not first_blocker:
        print("GLOBAL STOP: CLEAN_IDLE. All tasks completed.")
        sys.exit(0)
        
    next_task = safe_executable_tasks[0] if safe_executable_tasks else tasks[0]
    print(f"Selected Next Action: {next_task['instruction']}")
    
    manifest = FileManifestTracker.build_manifest([str(ledger_path.resolve())], repo_dir)
    dedupe_engine = TaskDedupeEngine(repo_dir)
    task_hash = dedupe_engine.compute_task_hash(
        task_type="continuation",
        instruction=next_task["instruction"],
        target_agent="Google-Antigravity",
        input_files=[str(ledger_path.resolve())]
    )
    
    context_delta = {"file_manifest": manifest, "task_dedupe_hash": task_hash}
    package = ChiefContextPackageBuilder.build_compact_package(
        workflow_id=record.get("GOAL"),
        task_id=next_task["id"],
        instruction=next_task["instruction"],
        scope_files=[str(ledger_path.resolve())],
        context_version=1,
        context_delta=context_delta,
        repo_dir=repo_dir
    )
    
    print("\n--- MINIMAL TASK PACKET ---")
    print(json.dumps(package, indent=2))
    
if __name__ == "__main__":
    main()
