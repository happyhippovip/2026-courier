"""Work Queue Ledger Compaction and Snapshot Engine (P30)

Provides high-efficiency state snapshotting and compaction for the append-only
JSONL work queue ledger, collapsing historical lifecycle transitions while
preserving fail-closed verification and cryptographic checksum integrity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CompactStateRecord:
    item_id: str
    status: str
    last_holder: Optional[str] = None
    expires_at: Optional[str] = None
    event_count: int = 0
    last_updated: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "status": self.status,
            "last_holder": self.last_holder,
            "expires_at": self.expires_at,
            "event_count": self.event_count,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CompactStateRecord:
        return cls(
            item_id=str(data.get("item_id", "")),
            status=str(data.get("status", "")),
            last_holder=data.get("last_holder"),
            expires_at=data.get("expires_at"),
            event_count=int(data.get("event_count", 0)),
            last_updated=data.get("last_updated"),
        )


def _canonical_records_hash(records: Dict[str, CompactStateRecord], total_events: int) -> str:
    canonical_dict = {
        "total_events": total_events,
        "records": {k: records[k].to_dict() for k in sorted(records.keys())},
    }
    canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


@dataclass
class LedgerSnapshot:
    snapshot_id: str
    created_at: str
    total_events_compacted: int
    records: Dict[str, CompactStateRecord] = field(default_factory=dict)
    checksum_sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at,
            "total_events_compacted": self.total_events_compacted,
            "checksum_sha256": self.checksum_sha256,
            "records": {k: r.to_dict() for k, r in sorted(self.records.items())},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LedgerSnapshot:
        raw_records = data.get("records", {})
        records = {k: CompactStateRecord.from_dict(v) for k, v in raw_records.items()}
        return cls(
            snapshot_id=str(data.get("snapshot_id", "")),
            created_at=str(data.get("created_at", "")),
            total_events_compacted=int(data.get("total_events_compacted", 0)),
            records=records,
            checksum_sha256=str(data.get("checksum_sha256", "")),
        )


def apply_event_to_record(
    current: Optional[CompactStateRecord],
    event: Dict[str, Any]
) -> CompactStateRecord:
    event_type = event.get("event_type", "").upper()
    item_id = str(event.get("item_id", ""))
    holder = event.get("holder")
    timestamp = event.get("timestamp") or datetime.now(timezone.utc).isoformat()

    prev_count = current.event_count if current else 0

    if event_type == "CLAIM":
        return CompactStateRecord(
            item_id=item_id,
            status="CLAIMED",
            last_holder=holder,
            expires_at=event.get("expires_at"),
            event_count=prev_count + 1,
            last_updated=timestamp,
        )
    elif event_type == "RENEW":
        return CompactStateRecord(
            item_id=item_id,
            status="CLAIMED",
            last_holder=holder,
            expires_at=event.get("expires_at"),
            event_count=prev_count + 1,
            last_updated=timestamp,
        )
    elif event_type == "RELEASE":
        result_status = event.get("result", "DONE")
        return CompactStateRecord(
            item_id=item_id,
            status=result_status,
            last_holder=holder,
            expires_at=None,
            event_count=prev_count + 1,
            last_updated=timestamp,
        )
    else:
        # Unknown or pass-through event
        status = current.status if current else "UNKNOWN"
        return CompactStateRecord(
            item_id=item_id,
            status=status,
            last_holder=holder or (current.last_holder if current else None),
            expires_at=current.expires_at if current else None,
            event_count=prev_count + 1,
            last_updated=timestamp,
        )


def rebuild_ledger_state(
    ledger_path: Path | str,
    start_line: int = 0,
    initial_state: Optional[Dict[str, CompactStateRecord]] = None
) -> Tuple[Dict[str, CompactStateRecord], int]:
    state: Dict[str, CompactStateRecord] = dict(initial_state or {})
    path = Path(ledger_path)
    if not path.exists():
        return state, 0

    total_events = 0
    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            total_events += 1
            if idx < start_line:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            item_id = ev.get("item_id")
            if not item_id:
                continue
            current = state.get(item_id)
            state[item_id] = apply_event_to_record(current, ev)

    return state, total_events


class LedgerCompactor:
    """Orchestrates creation, validation, and incremental replay of ledger snapshots."""

    def create_snapshot(self, ledger_path: Path | str, snapshot_path: Path | str) -> LedgerSnapshot:
        state, total_events = rebuild_ledger_state(ledger_path)
        checksum = _canonical_records_hash(state, total_events)

        now_iso = datetime.now(timezone.utc).isoformat()
        snapshot = LedgerSnapshot(
            snapshot_id=f"snap_{int(time.time())}",
            created_at=now_iso,
            total_events_compacted=total_events,
            records=state,
            checksum_sha256=checksum,
        )

        out_path = Path(snapshot_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_file = tempfile.mkstemp(
            prefix="snap_tmp_",
            suffix=".json",
            dir=str(out_path.parent)
        )
        try:
            with open(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(snapshot.to_dict(), f, indent=2)
            os.replace(tmp_file, str(out_path))
        except Exception:
            if os.path.exists(tmp_file):
                try:
                    os.unlink(tmp_file)
                except OSError:
                    pass
            raise

        return snapshot

    def load_snapshot(self, snapshot_path: Path | str) -> LedgerSnapshot:
        path = Path(snapshot_path)
        if not path.exists():
            raise FileNotFoundError(f"Snapshot file not found: {path}")

        data = json.loads(path.read_text(encoding="utf-8"))
        snapshot = LedgerSnapshot.from_dict(data)

        # Validate checksum
        expected_checksum = _canonical_records_hash(
            snapshot.records,
            snapshot.total_events_compacted
        )
        if snapshot.checksum_sha256 != expected_checksum:
            raise ValueError(
                f"Checksum mismatch: stored '{snapshot.checksum_sha256}' != computed '{expected_checksum}'"
            )

        return snapshot

    def verify_equivalence(
        self,
        ledger_path: Path | str,
        snapshot_path: Path | str
    ) -> Tuple[bool, List[str]]:
        """Verify that the snapshot matches full replay of the ledger up to the compacted point."""
        snapshot = self.load_snapshot(snapshot_path)
        full_state, total_events = rebuild_ledger_state(ledger_path)

        diffs: List[str] = []

        if snapshot.total_events_compacted != total_events:
            diffs.append(
                f"Event count mismatch: snapshot compacted {snapshot.total_events_compacted}, full ledger has {total_events}"
            )

        all_keys = set(snapshot.records.keys()) | set(full_state.keys())
        for k in sorted(all_keys):
            if k not in snapshot.records:
                diffs.append(f"Item '{k}' missing from snapshot")
            elif k not in full_state:
                diffs.append(f"Item '{k}' missing from full ledger")
            else:
                s_rec = snapshot.records[k]
                f_rec = full_state[k]
                if s_rec.status != f_rec.status:
                    diffs.append(f"Item '{k}' status mismatch: {s_rec.status} != {f_rec.status}")
                if s_rec.last_holder != f_rec.last_holder:
                    diffs.append(f"Item '{k}' holder mismatch: {s_rec.last_holder} != {f_rec.last_holder}")
                if s_rec.event_count != f_rec.event_count:
                    diffs.append(f"Item '{k}' event_count mismatch: {s_rec.event_count} != {f_rec.event_count}")

        return len(diffs) == 0, diffs

    def replay_with_delta(
        self,
        snapshot_path: Path | str,
        ledger_path: Path | str
    ) -> Dict[str, CompactStateRecord]:
        """Fast recovery: loads verified snapshot and processes only remaining delta lines."""
        snapshot = self.load_snapshot(snapshot_path)
        updated_state, _ = rebuild_ledger_state(
            ledger_path,
            start_line=snapshot.total_events_compacted,
            initial_state=snapshot.records
        )
        return updated_state


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Ledger Compactor & Snapshot CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    compact_parser = subparsers.add_parser("compact", help="Create a compacted state snapshot")
    compact_parser.add_argument("--ledger", required=True, help="Path to ledger JSONL file")
    compact_parser.add_argument("--snapshot", required=True, help="Output path for snapshot JSON")

    verify_parser = subparsers.add_parser("verify", help="Verify snapshot equivalence against ledger")
    verify_parser.add_argument("--ledger", required=True, help="Path to ledger JSONL file")
    verify_parser.add_argument("--snapshot", required=True, help="Path to snapshot JSON")

    args = parser.parse_args(argv)
    compactor = LedgerCompactor()

    if args.command == "compact":
        snap = compactor.create_snapshot(args.ledger, args.snapshot)
        print(json.dumps({
            "status": "COMPACTED",
            "snapshot_id": snap.snapshot_id,
            "total_events_compacted": snap.total_events_compacted,
            "items_count": len(snap.records),
            "checksum_sha256": snap.checksum_sha256,
        }, indent=2))
        return 0

    elif args.command == "verify":
        equiv, diffs = compactor.verify_equivalence(args.ledger, args.snapshot)
        print(json.dumps({
            "equivalent": equiv,
            "diff_count": len(diffs),
            "differences": diffs,
        }, indent=2))
        return 0 if equiv else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
