#!/usr/bin/env python3
"""Builds minimal, deterministic Handoff Context Packages for Chief-to-Antigravity execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_DIR = Path(__file__).resolve().parent.parent

try:
    from scripts.resource_policy import (
        ChiefContextPackageBuilder,
        FileManifestTracker,
        TaskDedupeEngine,
    )
except ImportError:
    from resource_policy import (
        ChiefContextPackageBuilder,
        FileManifestTracker,
        TaskDedupeEngine,
    )


def build_package(
    workflow_id: str,
    task_id: str,
    instruction: str,
    files: list[str] | None = None,
    repo_dir: Path | None = None,
) -> dict[str, Any]:
    if not workflow_id or not isinstance(workflow_id, str):
        raise ValueError("workflow_id must be a non-empty string")
    if not task_id or not isinstance(task_id, str):
        raise ValueError("task_id must be a non-empty string")
    if not instruction or not isinstance(instruction, str):
        raise ValueError("instruction must be a non-empty string")

    target_repo = repo_dir or REPO_DIR
    target_files = list(files) if files else []

    # 1. Build File/Diff Manifest
    manifest = FileManifestTracker.build_manifest(target_files, target_repo)

    # 2. Compute Dedupe Hash
    dedupe_engine = TaskDedupeEngine(target_repo)
    task_hash = dedupe_engine.compute_task_hash(
        task_type="handoff",
        instruction=instruction,
        target_agent="Google-Antigravity",
        input_files=target_files,
    )

    # 3. Build Minimal Context Package
    context_delta = {"file_manifest": manifest, "task_dedupe_hash": task_hash}
    package = ChiefContextPackageBuilder.build_compact_package(
        workflow_id=workflow_id,
        task_id=task_id,
        instruction=instruction,
        scope_files=target_files,
        context_version=1,
        context_delta=context_delta,
        repo_dir=target_repo,
    )

    return package


def main(argv: list[str] | None = None) -> int:
    args_list = argv if argv is not None else sys.argv[1:]

    # Support both positional legacy syntax and flagged syntax
    if args_list and not args_list[0].startswith("-"):
        if len(args_list) < 3:
            print("Usage: build_handoff_package.py <workflow_id> <task_id> <instruction> [files...]", file=sys.stderr)
            return 1
        workflow_id = args_list[0]
        task_id = args_list[1]
        instruction = args_list[2]
        files = args_list[3:]
        repo_dir = None
    else:
        parser = argparse.ArgumentParser(description="Build Chief-to-Worker Handoff Package")
        parser.add_argument("--workflow-id", required=True, help="Workflow execution ID")
        parser.add_argument("--task-id", required=True, help="Task identifier")
        parser.add_argument("--instruction", required=True, help="Command instruction")
        parser.add_argument("--files", nargs="*", default=[], help="Scoped files")
        parser.add_argument("--repo-dir", help="Path to repository root")
        parser.add_argument("--json", action="store_true", help="Format JSON output")
        parsed = parser.parse_args(args_list)

        workflow_id = parsed.workflow_id
        task_id = parsed.task_id
        instruction = parsed.instruction
        files = parsed.files
        repo_dir = Path(parsed.repo_dir).resolve() if parsed.repo_dir else None

    try:
        package = build_package(
            workflow_id=workflow_id,
            task_id=task_id,
            instruction=instruction,
            files=files,
            repo_dir=repo_dir,
        )
        print(json.dumps(package, indent=2))
        return 0
    except Exception as exc:
        print(f"BUILD_HANDOFF_PACKAGE_ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
