"""Summarize accepted results for one Courier home (P2).

Read-only, fail-closed digest of all accepted task outcomes and artifacts
recorded in <home>/courier.db. Produces a deterministic, cryptographic
digest that can be attested across restarts or verified by external tooling.
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
from typing import Any, Mapping

from courier_core.events import EventType, canonical_json


@dataclass(frozen=True)
class AcceptedArtifact:
    path: str
    sha256: str


@dataclass(frozen=True)
class AcceptedTaskSummary:
    task_id: str
    result_id: str
    dispatch_id: str
    attempt: int
    outcome: str
    adapter: str
    artifacts: list[dict[str, str]]
    accepted_at: str


@dataclass(frozen=True)
class ResultDigest:
    status: str  # "OK", "EMPTY", "NOT_FOUND", "CORRUPT"
    home: str
    total_accepted: int = 0
    total_artifacts: int = 0
    adapters: list[str] = field(default_factory=list)
    tasks: list[dict[str, Any]] = field(default_factory=list)
    digest_sha256: str = ""
    error_detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "home": self.home,
            "total_accepted": self.total_accepted,
            "total_artifacts": self.total_artifacts,
            "adapters": self.adapters,
            "tasks": self.tasks,
            "digest_sha256": self.digest_sha256,
            "error_detail": self.error_detail,
        }


def _compute_digest_sha256(tasks_data: list[dict[str, Any]]) -> str:
    """Compute deterministic SHA-256 over the canonical JSON of accepted tasks."""
    serialized = canonical_json(tasks_data)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def summarize_home(home: Path | str) -> ResultDigest:
    """Extract and summarize all accepted task results from one Courier home."""
    home_path = Path(home).resolve()
    db_path = home_path / "courier.db"

    if not home_path.exists() or not db_path.exists():
        return ResultDigest(
            status="NOT_FOUND",
            home=str(home_path),
            error_detail=f"Database file not found: {db_path}",
        )

    try:
        # Open in read-only mode so this never acquires exclusive locks or mutates the journal
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("PRAGMA query_only = ON;")
    except sqlite3.Error as exc:
        return ResultDigest(
            status="CORRUPT",
            home=str(home_path),
            error_detail=f"Failed to open database in read-only mode: {exc}",
        )

    try:
        # Check if events table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='events';"
        )
        if not cursor.fetchone():
            conn.close()
            return ResultDigest(
                status="EMPTY",
                home=str(home_path),
                error_detail="Journal events table not found",
            )

        # Retrieve all RESULT_ACCEPTED events ordered by seq
        cursor.execute(
            """
            SELECT seq, task_id, attempt, dispatch_id, result_id, ts_utc, payload
            FROM events
            WHERE type = ?
            ORDER BY seq ASC;
            """,
            (EventType.RESULT_ACCEPTED.value,),
        )
        accepted_rows = cursor.fetchall()

        if not accepted_rows:
            conn.close()
            return ResultDigest(
                status="OK",
                home=str(home_path),
                total_accepted=0,
                total_artifacts=0,
                adapters=[],
                tasks=[],
                digest_sha256=hashlib.sha256(b"[]").hexdigest(),
            )

        # Build mapping of task_id -> adapter from TASK_CREATED
        cursor.execute(
            """
            SELECT task_id, payload
            FROM events
            WHERE type = ?;
            """,
            (EventType.TASK_CREATED.value,),
        )
        task_adapters: dict[str, str] = {}
        for row in cursor.fetchall():
            try:
                p = json.loads(row["payload"])
                task_adapters[row["task_id"]] = p.get("adapter", "unknown")
            except (json.JSONDecodeError, TypeError):
                continue

        # Build mapping of (dispatch_id, result_id) -> RESULT_READY payload (outcome, artifacts)
        cursor.execute(
            """
            SELECT dispatch_id, result_id, payload
            FROM events
            WHERE type = ?;
            """,
            (EventType.RESULT_READY.value,),
        )
        results_ready: dict[tuple[str, str], dict[str, Any]] = {}
        for row in cursor.fetchall():
            try:
                p = json.loads(row["payload"])
                results_ready[(row["dispatch_id"], row["result_id"])] = p
            except (json.JSONDecodeError, TypeError):
                continue

        conn.close()

        summarized_tasks: list[dict[str, Any]] = []
        distinct_adapters: set[str] = set()
        total_artifacts_count = 0

        for row in accepted_rows:
            task_id = row["task_id"]
            dispatch_id = row["dispatch_id"]
            result_id = row["result_id"]
            attempt = row["attempt"]
            accepted_at = row["ts_utc"]

            ready_info = results_ready.get((dispatch_id, result_id), {})
            outcome = ready_info.get("outcome", "unknown")
            raw_artifacts = ready_info.get("artifacts", [])

            clean_artifacts: list[dict[str, str]] = []
            if isinstance(raw_artifacts, list):
                for art in raw_artifacts:
                    if isinstance(art, dict) and "path" in art and "sha256" in art:
                        clean_artifacts.append({
                            "path": str(art["path"]),
                            "sha256": str(art["sha256"]),
                        })

            total_artifacts_count += len(clean_artifacts)
            adapter = task_adapters.get(task_id, "unknown")
            distinct_adapters.add(adapter)

            summarized_tasks.append({
                "task_id": task_id,
                "result_id": result_id,
                "dispatch_id": dispatch_id,
                "attempt": attempt,
                "outcome": outcome,
                "adapter": adapter,
                "artifacts": clean_artifacts,
                "accepted_at": accepted_at,
            })

        # Sort tasks deterministically by task_id then result_id
        summarized_tasks.sort(key=lambda t: (t["task_id"], t["result_id"]))
        digest_hash = _compute_digest_sha256(summarized_tasks)

        return ResultDigest(
            status="OK",
            home=str(home_path),
            total_accepted=len(summarized_tasks),
            total_artifacts=total_artifacts_count,
            adapters=sorted(distinct_adapters),
            tasks=summarized_tasks,
            digest_sha256=digest_hash,
        )

    except sqlite3.DatabaseError as exc:
        try:
            conn.close()
        except Exception:
            pass
        return ResultDigest(
            status="CORRUPT",
            home=str(home_path),
            error_detail=f"Corrupt or unreadable database: {exc}",
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize accepted results for a Courier home.")
    parser.add_argument("--home", type=Path, default=None, help="Path to COURIER_HOME (defaults to env)")
    parser.add_argument("--json", action="store_true", help="Output summary as JSON")
    args = parser.parse_args(argv)

    home_dir = args.home or os.environ.get("COURIER_HOME")
    if not home_dir:
        print("Error: COURIER_HOME not provided via --home or environment", file=sys.stderr)
        return 2

    digest = summarize_home(home_dir)
    if args.json:
        print(canonical_json(digest.to_dict()))
    else:
        print(f"Status: {digest.status}")
        print(f"Home: {digest.home}")
        print(f"Total Accepted Tasks: {digest.total_accepted}")
        print(f"Total Artifacts: {digest.total_artifacts}")
        print(f"Adapters: {', '.join(digest.adapters) if digest.adapters else 'None'}")
        print(f"Digest SHA-256: {digest.digest_sha256}")
        if digest.error_detail:
            print(f"Detail: {digest.error_detail}")

    return 0 if digest.status in ("OK", "EMPTY") else 1


if __name__ == "__main__":
    sys.exit(main())
