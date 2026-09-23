#!/usr/bin/env python3
"""Resilient queue processor for revenue intakes with isolation and quarantine."""

import json
import os
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from intake_dispatcher import dispatch_intake


def process_queue(
    pending_dir="intakes/pending",
    processed_dir="intakes/processed",
    failed_dir="intakes/failed",
    state_file=None,
    gh_runner=None,
) -> dict:
    p_dir = Path(pending_dir)
    proc_dir = Path(processed_dir)
    f_dir = Path(failed_dir)

    p_dir.mkdir(parents=True, exist_ok=True)
    proc_dir.mkdir(parents=True, exist_ok=True)
    f_dir.mkdir(parents=True, exist_ok=True)

    pending_files = sorted(p_dir.glob("*.json"))
    results = []
    processed_count = 0
    failed_count = 0

    for intake_file in pending_files:
        print(f"Processing {intake_file.name}", flush=True)
        try:
            res = dispatch_intake(intake_file, state_file=state_file, gh_runner=gh_runner)
            dest = proc_dir / intake_file.name
            shutil.move(str(intake_file), str(dest))
            print(f"Successfully processed and moved {intake_file.name} to {proc_dir}", flush=True)
            results.append({"file": intake_file.name, "status": "PROCESSED", "task_id": res.get("task_id")})
            processed_count += 1
        except Exception as exc:
            print(f"Error processing {intake_file.name}: {exc}", file=sys.stderr, flush=True)
            # Quarantine failing intake to prevent queue poison loop
            failed_dest = f_dir / intake_file.name
            shutil.move(str(intake_file), str(failed_dest))
            # Save error record alongside quarantined file
            err_file = f_dir / f"{intake_file.stem}.error.json"
            err_payload = {
                "file": intake_file.name,
                "error": str(exc),
                "failed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            try:
                err_file.write_text(json.dumps(err_payload, indent=2) + "\n", encoding="utf-8")
            except OSError:
                pass
            results.append({"file": intake_file.name, "status": "FAILED", "error": str(exc)})
            failed_count += 1

    return {
        "total_scanned": len(pending_files),
        "processed": processed_count,
        "failed": failed_count,
        "results": results,
    }


if __name__ == "__main__":
    summary = process_queue()
    print(f"Queue cycle complete: {summary['processed']} processed, {summary['failed']} failed.")
