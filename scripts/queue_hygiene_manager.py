#!/usr/bin/env python3
"""Mission 193: Opportunity Queue Hygiene & Archival Manager.

Prunes completed historical mission tasks from active queue files and archives
them into a durable historical ledger with cryptographic fingerprint preservation:
- Never archives READY, CLAIMED, RUNNING, WAITING_FOR_HUMAN, PAYMENT_APPROVAL_REQUIRED, or UNKNOWN
- Quarantines corrupt items
- Retains completion fingerprints to ensure completed work cannot accidentally become READY again
- 100% deterministic, 0 model spend
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from opportunity_queue import Opportunity, OpportunityQueue
except ImportError:
    from scripts.opportunity_queue import Opportunity, OpportunityQueue


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:6]}")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


PROTECTED_ACTIVE_STATUSES = {
    "READY",
    "CLAIMED",
    "RUNNING",
    "WAITING_FOR_HUMAN",
    "PAYMENT_APPROVAL_REQUIRED",
    "RECOVERY_REQUIRED",
    "UNKNOWN",
}


@dataclass
class ArchivedOpportunityRecord:
    opportunity_id: str
    source: str
    objective_id: str
    project: str
    description: str
    priority: int
    target_agent: str
    status: str
    completion_fingerprint: str
    completed_at: str
    result_reference: Optional[str] = None
    original_payload: Dict[str, Any] = field(default_factory=dict)
    archived_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class QueueHygieneManager:
    """Manages safe archival and historical ledger tracking for OpportunityQueue."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir.resolve()
        self.queue_dir = self.repo_dir / "events" / "opportunity-queue"
        self.archive_dir = self.queue_dir / "archive"
        self.quarantine_dir = self.queue_dir / "quarantine"
        self.ledger_file = self.queue_dir / "historical_ledger.json"
        self.manifest_file = self.queue_dir / "archive_manifest.json"

        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def compute_completion_fingerprint(cls, opp: Opportunity) -> str:
        """Deterministic fingerprint proving completion truth for duplicate suppression."""
        raw = f"{opp.opportunity_id}|{opp.objective_id}|{opp.project}|{opp.description}|{opp.status}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def inspect_queue(self) -> Dict[str, Any]:
        """Scans queue directory and returns item counts by status and safety."""
        q = OpportunityQueue(repo_dir=self.repo_dir)
        all_opps = q.list_opportunities()

        by_status: Dict[str, List[Opportunity]] = {}
        for opp in all_opps:
            by_status.setdefault(opp.status, []).append(opp)

        corrupt_files = []
        for f in self.queue_dir.glob("OPP-*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or "opportunity_id" not in data:
                    corrupt_files.append(str(f))
            except Exception:
                corrupt_files.append(str(f))

        return {
            "total_count": len(all_opps),
            "by_status": {k: len(v) for k, v in by_status.items()},
            "completed_count": len(by_status.get("COMPLETED", [])),
            "actionable_count": sum(len(v) for k, v in by_status.items() if k in PROTECTED_ACTIVE_STATUSES),
            "corrupt_files": corrupt_files,
        }

    def prune_and_archive_completed(self) -> Dict[str, Any]:
        """Safely archives all COMPLETED items into historical ledger and prunes active queue."""
        q = OpportunityQueue(repo_dir=self.repo_dir)
        all_opps = q.list_opportunities()

        # Load existing historical ledger
        ledger_data = load_json(self.ledger_file)
        historical_records: Dict[str, Any] = ledger_data.get("records", {})

        completed_to_archive: List[Opportunity] = []
        protected_remaining: List[Opportunity] = []
        corrupt_quarantined: List[str] = []

        # 1. Quarantine corrupt files
        for f in self.queue_dir.glob("OPP-*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or "opportunity_id" not in data:
                    target_quarantine = self.quarantine_dir / f.name
                    shutil.move(str(f), str(target_quarantine))
                    corrupt_quarantined.append(f.name)
            except Exception:
                target_quarantine = self.quarantine_dir / f.name
                shutil.move(str(f), str(target_quarantine))
                corrupt_quarantined.append(f.name)

        # 2. Partition completed vs protected items
        for opp in all_opps:
            if opp.status == "COMPLETED":
                completed_to_archive.append(opp)
            else:
                protected_remaining.append(opp)

        # 3. Archive completed items into individual files & consolidated ledger
        archived_ids: List[str] = []
        for opp in completed_to_archive:
            fp = self.compute_completion_fingerprint(opp)
            record = ArchivedOpportunityRecord(
                opportunity_id=opp.opportunity_id,
                source=opp.source,
                objective_id=opp.objective_id,
                project=opp.project,
                description=opp.description,
                priority=opp.priority,
                target_agent=opp.target_agent,
                status=opp.status,
                completion_fingerprint=fp,
                completed_at=opp.evidence.get("completed_at", utc_now()) if isinstance(opp.evidence, dict) else utc_now(),
                result_reference=opp.evidence.get("result_reference") if isinstance(opp.evidence, dict) else None,
                original_payload=opp.to_dict(),
                archived_at=utc_now(),
            )

            # Write individual archive file
            archive_file = self.archive_dir / f"{opp.opportunity_id}.json"
            write_json(archive_file, record.to_dict())

            # Store in historical ledger
            historical_records[opp.opportunity_id] = record.to_dict()
            archived_ids.append(opp.opportunity_id)

            # Unlink individual OPP file from active directory if it existed
            individual_file = self.queue_dir / f"{opp.opportunity_id}.json"
            if individual_file.is_file():
                individual_file.unlink(missing_ok=True)

        # 4. Save consolidated historical ledger
        write_json(
            self.ledger_file,
            {
                "schema_version": "3.0",
                "updated_at": utc_now(),
                "description": "Consolidated historical ledger for completed and superseded opportunities",
                "total_archived_count": len(historical_records),
                "records": historical_records,
            },
        )

        # 5. Update active opportunities.json so it only contains protected actionable work
        active_map = {opp.opportunity_id: opp.to_dict() for opp in protected_remaining}
        write_json(self.queue_dir / "opportunities.json", active_map)

        # 6. Build archive manifest for verification
        manifest = {
            "manifest_version": "3.0",
            "generated_at": utc_now(),
            "active_count": len(protected_remaining),
            "archived_count": len(completed_to_archive),
            "total_ledger_count": len(historical_records),
            "active_opportunity_ids": [opp.opportunity_id for opp in protected_remaining],
            "archived_opportunity_ids": archived_ids,
            "corrupt_quarantined": corrupt_quarantined,
            "fingerprints_hash": hashlib.sha256(
                ",".join(sorted(r["completion_fingerprint"] for r in historical_records.values())).encode("utf-8")
            ).hexdigest(),
        }
        write_json(self.manifest_file, manifest)

        return {
            "status": "SUCCESS",
            "archived_count": len(completed_to_archive),
            "active_remaining_count": len(protected_remaining),
            "corrupt_quarantined_count": len(corrupt_quarantined),
            "total_ledger_count": len(historical_records),
            "manifest": manifest,
        }

    def is_task_completed_in_history(self, opportunity_id: str) -> bool:
        """Verifies if a task was historically completed to prevent accidental re-execution."""
        ledger = load_json(self.ledger_file)
        records = ledger.get("records", {})
        return opportunity_id in records

    def prune_stale_claims(self, max_age_seconds: float = 1800.0) -> int:
        """Prunes dead claims whose owner PID is dead or timestamp is older than max_age_seconds."""
        claims_dir = self.queue_dir / "claims"
        if not claims_dir.is_dir():
            return 0
        pruned = 0
        now = dt.datetime.now(dt.timezone.utc)
        for claim_file in claims_dir.glob("*.json"):
            try:
                data = json.loads(claim_file.read_text(encoding="utf-8"))
                pid = data.get("pid")
                claimed_at = data.get("claimed_at")
                is_dead = False
                if pid:
                    try:
                        os.kill(int(pid), 0)
                    except (ProcessLookupError, ValueError):
                        is_dead = True
                    except PermissionError:
                        is_dead = False
                if claimed_at:
                    try:
                        c_dt = dt.datetime.fromisoformat(claimed_at)
                        if c_dt.tzinfo is None:
                            c_dt = c_dt.replace(tzinfo=dt.timezone.utc)
                        if (now - c_dt).total_seconds() > max_age_seconds:
                            is_dead = True
                    except Exception:
                        pass
                if is_dead:
                    claim_file.unlink(missing_ok=True)
                    pruned += 1
            except Exception:
                pass
        return pruned


def main() -> int:
    parser = argparse.ArgumentParser(description="Queue Hygiene & Archival Manager (Mission 193)")
    parser.add_argument("--prune", action="store_true", help="Execute pruning and archival of completed tasks")
    parser.add_argument("--inspect", action="store_true", help="Inspect current queue status")
    args = parser.parse_args()

    manager = QueueHygieneManager()
    if args.prune:
        res = manager.prune_and_archive_completed()
        print(json.dumps(res, indent=2))
        return 0

    status = manager.inspect_queue()
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
