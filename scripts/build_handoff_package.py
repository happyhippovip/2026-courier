#!/usr/bin/env python3
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from scripts.resource_policy import (
    ChiefContextPackageBuilder,
    FileManifestTracker,
    TaskDedupeEngine
)

def build_package(workflow_id, task_id, instruction, files):
    repo_dir = Path(__file__).parent.parent.resolve()
    
    # 1. Build File/Diff Manifest
    manifest = FileManifestTracker.build_manifest(files, repo_dir)
    
    # 2. Compute Dedupe Hash
    dedupe_engine = TaskDedupeEngine(repo_dir)
    task_hash = dedupe_engine.compute_task_hash(
        task_type="handoff", 
        instruction=instruction,
        target_agent="Google-Antigravity",
        input_files=files
    )
    
    # 3. Build Minimal Context Package
    context_delta = {"file_manifest": manifest, "task_dedupe_hash": task_hash}
    package = ChiefContextPackageBuilder.build_compact_package(
        workflow_id=workflow_id,
        task_id=task_id,
        instruction=instruction,
        scope_files=files,
        context_version=1,
        context_delta=context_delta,
        repo_dir=repo_dir
    )
    
    return package

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: build_handoff_package.py <workflow_id> <task_id> <instruction> [files...]")
        sys.exit(1)
        
    workflow_id = sys.argv[1]
    task_id = sys.argv[2]
    instruction = sys.argv[3]
    files = sys.argv[4:]
    
    package = build_package(workflow_id, task_id, instruction, files)
    print(json.dumps(package, indent=2))
