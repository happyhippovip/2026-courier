#!/usr/bin/env python3
"""Courier Queue Processor for Customer Intakes.

Processes pending JSON requests in intakes/pending, dispatches them via intake_dispatcher,
and atomically moves them to intakes/processed (or intakes/failed on unrecoverable error).
"""

import argparse
import glob
import json
import os
import sys
from pathlib import Path

# Ensure we can import from scripts dir
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from intake_dispatcher import dispatch_intake


def process_queue(
    repo_dir: str | Path | None = None,
    dry_run: bool = False,
    quiet: bool = False,
) -> list[dict]:
    if repo_dir is None:
        repo_dir = Path(__file__).resolve().parent.parent
    else:
        repo_dir = Path(repo_dir).resolve()

    pending_dir = repo_dir / "intakes" / "pending"
    processed_dir = repo_dir / "intakes" / "processed"
    failed_dir = repo_dir / "intakes" / "failed"

    pending_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    pending_files = sorted(glob.glob(str(pending_dir / "*.json")))
    if not pending_files:
        return []

    results = []
    for intake_path_str in pending_files:
        intake_file = Path(intake_path_str)
        if not quiet:
            print(f"Processing {intake_file.name}")
        try:
            res = dispatch_intake(
                str(intake_file),
                repo_dir=str(repo_dir),
                dry_run=dry_run,
                quiet=quiet,
            )
            dest = processed_dir / intake_file.name
            if dest.exists():
                try:
                    dest.unlink()
                except Exception:
                    pass
            os.replace(str(intake_file), str(dest))
            if not quiet:
                print(f"Successfully processed and moved {intake_file.name}")
            results.append({
                "file": intake_file.name,
                "status": "PROCESSED",
                "result": res,
            })
        except Exception as e:
            if not quiet:
                print(f"Error processing {intake_file.name}: {e}")
            dest = failed_dir / intake_file.name
            if dest.exists():
                try:
                    dest.unlink()
                except Exception:
                    pass
            try:
                os.replace(str(intake_file), str(dest))
            except Exception:
                pass
            results.append({
                "file": intake_file.name,
                "status": "FAILED",
                "error": str(e),
            })

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Process queued customer intakes")
    parser.add_argument("--repo-dir", help="Path to repository root")
    parser.add_argument("--dry-run", action="store_true", help="Simulate dispatch without GitHub call")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args(argv)

    results = process_queue(repo_dir=args.repo_dir, dry_run=args.dry_run, quiet=args.json)
    if args.json:
        print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
