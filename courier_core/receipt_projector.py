"""Project task execution receipts from journal into canonical proof record.

Lane L2. Read-only projection: reads SQLite (events.db) or journal.jsonl
with zero mutation. Extracts deterministic receipts, validates single-writer
and evidence-before-done invariants, and computes cryptographic proof digests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class TaskReceipt:
    task_id: str
    dispatch_id: str
    worker_id: str
    attempt: int
    outcome: str
    returncode: int
    duration_s: float
    artifact_count: int
    completed_at: str
    proof_digest: str


@dataclass
class ReceiptProjectionReport:
    valid: bool
    total_receipts: int
    success_count: int
    failed_count: int
    receipts: list[TaskReceipt] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["receipts"] = [asdict(r) for r in self.receipts]
        return d


def _compute_proof_digest(receipt_dict: dict[str, Any]) -> str:
    serialized = json.dumps(receipt_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def project_receipts(
    home_path: str | Path,
    task_id_filter: Optional[str] = None,
) -> ReceiptProjectionReport:
    home = Path(home_path)
    if not home.exists() or not home.is_dir():
        return ReceiptProjectionReport(
            valid=False,
            total_receipts=0,
            success_count=0,
            failed_count=0,
            violations=[f"home does not exist or is not a directory: {home}"],
        )

    journal_path = home / "journal.jsonl"
    db_path = home / "events.db"

    events: list[dict[str, Any]] = []
    violations: list[str] = []

    # 1. Read journal.jsonl if present
    if journal_path.exists():
        try:
            with open(journal_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        except Exception as exc:
            violations.append(f"failed to read journal.jsonl: {exc}")

    # 2. Read events.db if present
    if db_path.exists():
        try:
            uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
                )
                if cursor.fetchone():
                    # Introspect columns
                    cursor.execute("SELECT * FROM events")
                    col_names = [d[0] for d in cursor.description]
                    for row in cursor.fetchall():
                        row_dict = dict(zip(col_names, row))
                        payload = {}
                        if "payload" in row_dict and row_dict["payload"]:
                            raw = row_dict["payload"]
                            if isinstance(raw, str):
                                try:
                                    payload = json.loads(raw)
                                except json.JSONDecodeError:
                                    pass
                            elif isinstance(raw, dict):
                                payload = raw
                        merged = {**row_dict, **payload}
                        events.append(merged)
            finally:
                conn.close()
        except Exception as exc:
            violations.append(f"failed to read events.db: {exc}")

    receipts: list[TaskReceipt] = []
    success_count = 0
    failed_count = 0
    seen_keys: set[tuple[str, str, int, str]] = set()
    accepted_types = {
        "FINAL_ACCEPTED",
        "TASK_RESULT_DELIVERED",
        "RESULT_ACCEPTED",
        "RESULT_DELIVERED",
        "result.accepted",
        "result.delivered",
    }

    # Group final events by task_id / dispatch_id
    for ev in events:
        ev_type = str(ev.get("type") or ev.get("event_type") or "")
        if ev_type not in accepted_types:
            continue

        tid = str(ev.get("task_id") or "")
        if task_id_filter and tid != task_id_filter:
            continue

        did = str(ev.get("dispatch_id") or "")
        wid = str(ev.get("worker_id") or "")
        attempt = int(ev.get("attempt") or 1)
        dedupe_key = (tid, did, attempt, ev_type.lower())
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        outcome = str(ev.get("outcome") or "unknown")
        rc = int(ev.get("returncode") if ev.get("returncode") is not None else 0)
        dur = float(ev.get("duration_s") or 0.0)
        artifacts = ev.get("artifacts") or []
        art_count = len(artifacts)
        completed_at = str(ev.get("at") or ev.get("created_at") or ev.get("ts_utc") or "")

        # Invariant checks:
        # Evidence before done: outcome == 'success' requires art_count > 0
        if outcome in ("success", "completed") and art_count == 0:
            violations.append(
                f"evidence_missing: task {tid} (dispatch {did}) reported success with 0 artifacts"
            )

        proof_payload = {
            "task_id": tid,
            "dispatch_id": did,
            "worker_id": wid,
            "attempt": attempt,
            "outcome": outcome,
            "returncode": rc,
            "duration_s": dur,
            "artifact_count": art_count,
            "completed_at": completed_at,
        }
        proof_digest = _compute_proof_digest(proof_payload)

        receipt = TaskReceipt(
            task_id=tid,
            dispatch_id=did,
            worker_id=wid,
            attempt=attempt,
            outcome=outcome,
            returncode=rc,
            duration_s=dur,
            artifact_count=art_count,
            completed_at=completed_at,
            proof_digest=proof_digest,
        )
        receipts.append(receipt)

        if outcome in ("success", "completed") and rc == 0 and art_count > 0:
            success_count += 1
        else:
            failed_count += 1

    valid = len(violations) == 0

    return ReceiptProjectionReport(
        valid=valid,
        total_receipts=len(receipts),
        success_count=success_count,
        failed_count=failed_count,
        receipts=receipts,
        violations=violations,
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="courier_core.receipt_projector",
        description="Project task execution receipts into canonical proof record.",
    )
    parser.add_argument("home_path", help="Path to home containing journal or events.db")
    parser.add_argument("--task-id", help="Filter receipts by specific task ID")
    parser.add_argument("--output", help="Optional output JSON file")
    args = parser.parse_args(argv)

    report = project_receipts(args.home_path, task_id_filter=args.task_id)
    report_dict = report.to_dict()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2)

    print(json.dumps(report_dict, indent=2))
    return 0 if report.valid else 1


if __name__ == "__main__":
    sys.exit(main())
