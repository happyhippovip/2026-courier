"""Read-only local task summary from the append-only journal (no controller required)."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from courier_core.journal import Journal, JournalError
from courier_core.state_machine import TERMINAL, TaskStatus


def _inspect(home: Path) -> dict:
    db = home / "courier.db"
    if not db.exists():
        return {
            "ok": False,
            "code": "no_journal",
            "message": "No local journal (courier.db) in this home.",
        }
    journal = Journal(db, readonly=True)
    try:
        try:
            journal.open()
        except (JournalError, sqlite3.Error, OSError) as exc:
            return {"ok": False, "code": "journal_error", "message": str(exc)}

        try:
            chain = journal.verify_chain()
            if not chain.ok:
                return {
                    "ok": False,
                    "code": "journal_corrupt",
                    "message": chain.reason or "journal hash chain failed",
                    "first_bad_seq": chain.first_bad_seq,
                }
            tasks = journal.tasks()
            counts = Counter(t.status.value for t in tasks)
            active = [
                {
                    "task_id": t.task_id,
                    "status": t.status.value,
                    "adapter": t.adapter,
                    "attempt": t.attempt,
                }
                for t in tasks
                if t.status not in TERMINAL
            ]
            needs_attention = [
                t for t in active if t["status"] in (TaskStatus.BLOCKED.value, TaskStatus.RETRY_PENDING.value)
            ]
            return {
                "ok": True,
                "home": str(home),
                "head_seq": chain.head_seq,
                "task_counts": dict(sorted(counts.items())),
                "active_count": len(active),
                "needs_attention": needs_attention,
                "active_tasks": active[:32],
            }
        except (JournalError, sqlite3.Error, OSError) as exc:
            return {"ok": False, "code": "journal_error", "message": str(exc)}
    finally:
        journal.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="courier-core status",
                                     description="Summarize tasks from the local Courier journal (read-only).")
    parser.add_argument("--home", default=os.environ.get("COURIER_HOME"),
                        help="Courier home (default: $COURIER_HOME)")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)
    if not args.home:
        parser.error("--home or COURIER_HOME is required")
    home = Path(args.home).expanduser().resolve()
    report = _inspect(home)
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        if not report["ok"]:
            print(report["message"], file=sys.stderr)
        else:
            print(f"Journal OK at {report['home']} (head_seq={report['head_seq']})")
            if report["task_counts"]:
                parts = [f"{k}={v}" for k, v in report["task_counts"].items()]
                print("Tasks: " + ", ".join(parts))
            else:
                print("Tasks: (none)")
            if report["needs_attention"]:
                print("Needs attention:")
                for row in report["needs_attention"]:
                    print(f"  - {row['task_id']}: {row['status']} ({row['adapter']})")
            elif report["active_count"]:
                print(f"Active tasks: {report['active_count']} (none blocked or retry-pending)")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
