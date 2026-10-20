"""Dual-Channel Event Sourcing and Real-Time Replay Log.

Provides append-only persistence with monotonic sequence generation,
real-time subscriber publishing, SHA-256 checksum verification,
and snapshot compaction for fast state recovery.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable, Optional


class EventSourcingError(Exception):
    """Base exception for event sourcing operations."""


class CorruptedEventLogError(EventSourcingError):
    """Raised when an event checksum or sequence fails verification."""


@dataclass(frozen=True)
class JournalEvent:
    """An immutable event entry within the event sourcing log."""

    seq: int
    event_type: str
    aggregate_id: str
    data: dict[str, Any]
    timestamp: str
    checksum: str

    def canonical_bytes(self) -> bytes:
        payload = {
            "seq": self.seq,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return canonical_json.encode("utf-8")

    @classmethod
    def compute_checksum(cls, seq: int, event_type: str, aggregate_id: str, data: dict[str, Any], timestamp: str) -> str:
        payload = {
            "seq": seq,
            "event_type": event_type,
            "aggregate_id": aggregate_id,
            "data": data,
            "timestamp": timestamp,
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JournalEvent:
        return cls(
            seq=int(data["seq"]),
            event_type=str(data["event_type"]),
            aggregate_id=str(data["aggregate_id"]),
            data=dict(data.get("data", {})),
            timestamp=str(data["timestamp"]),
            checksum=str(data["checksum"]),
        )


@dataclass(frozen=True)
class Snapshot:
    """Compacted state representation up to a specific sequence number."""

    aggregate_id: str
    seq: int
    state: dict[str, Any]
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Snapshot:
        return cls(
            aggregate_id=str(data["aggregate_id"]),
            seq=int(data["seq"]),
            state=dict(data["state"]),
            timestamp=str(data["timestamp"]),
        )


class EventStore:
    """Append-only dual-channel event store with snapshotting support."""

    def __init__(self, store_path: str | Path) -> None:
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir = self.store_path.parent / (self.store_path.stem + "_snapshots")
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self._subscribers: list[Callable[[JournalEvent], None]] = []

    def subscribe(self, callback: Callable[[JournalEvent], None]) -> None:
        """Register a real-time callback subscriber."""
        self._subscribers.append(callback)

    def _get_last_seq(self) -> int:
        if not self.store_path.exists():
            return 0
        last_seq = 0
        with open(self.store_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        last_seq = max(last_seq, int(record.get("seq", 0)))
                    except Exception:
                        pass
        return last_seq

    def append(self, event_type: str, aggregate_id: str, data: dict[str, Any]) -> JournalEvent:
        """Append an event to the persistent log and publish to subscribers."""
        next_seq = self._get_last_seq() + 1
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        checksum = JournalEvent.compute_checksum(
            seq=next_seq,
            event_type=event_type,
            aggregate_id=aggregate_id,
            data=data,
            timestamp=now_iso,
        )

        event = JournalEvent(
            seq=next_seq,
            event_type=event_type,
            aggregate_id=aggregate_id,
            data=data,
            timestamp=now_iso,
            checksum=checksum,
        )

        # 1. Persistent Channel Flush
        with open(self.store_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict()) + "\n")
            f.flush()
            os.fsync(f.fileno())

        # 2. Real-Time Channel Broadcast
        for sub in self._subscribers:
            try:
                sub(event)
            except Exception:
                pass

        return event

    def replay(self, aggregate_id: Optional[str] = None, from_seq: int = 0) -> list[JournalEvent]:
        """Replay events from log, verifying checksums and filtering by aggregate/sequence."""
        if not self.store_path.exists():
            return []

        events: list[JournalEvent] = []
        with open(self.store_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                record = json.loads(line)
                event = JournalEvent.from_dict(record)

                # Verify checksum
                expected = JournalEvent.compute_checksum(
                    seq=event.seq,
                    event_type=event.event_type,
                    aggregate_id=event.aggregate_id,
                    data=event.data,
                    timestamp=event.timestamp,
                )
                if event.checksum != expected:
                    raise CorruptedEventLogError(
                        f"Checksum mismatch in event log at line {line_no} (seq={event.seq}): expected {expected}, got {event.checksum}"
                    )

                if event.seq > from_seq:
                    if aggregate_id is None or event.aggregate_id == aggregate_id:
                        events.append(event)

        return events

    def create_snapshot(self, aggregate_id: str, state: dict[str, Any], up_to_seq: int) -> Snapshot:
        """Create a state snapshot for fast resumption."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        snap = Snapshot(
            aggregate_id=aggregate_id,
            seq=up_to_seq,
            state=state,
            timestamp=now_iso,
        )
        snap_file = self.snapshots_dir / f"{aggregate_id}.json"
        with open(snap_file, "w", encoding="utf-8") as f:
            json.dump(snap.to_dict(), f, indent=2)
        return snap

    def get_snapshot(self, aggregate_id: str) -> Optional[Snapshot]:
        snap_file = self.snapshots_dir / f"{aggregate_id}.json"
        if not snap_file.exists():
            return None
        with open(snap_file, "r", encoding="utf-8") as f:
            return Snapshot.from_dict(json.load(f))

    def get_snapshot_and_deltas(self, aggregate_id: str) -> tuple[Optional[Snapshot], list[JournalEvent]]:
        """Fetch latest snapshot and subsequent uncompacted delta events."""
        snap = self.get_snapshot(aggregate_id)
        from_seq = snap.seq if snap else 0
        deltas = self.replay(aggregate_id=aggregate_id, from_seq=from_seq)
        return snap, deltas


def main() -> None:
    parser = argparse.ArgumentParser(description="Dual-Channel Event Sourcing Log")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # append
    app_p = subparsers.add_parser("append", help="Append an event to the store")
    app_p.add_argument("--store", required=True, help="Path to event log file")
    app_p.add_argument("--type", required=True, help="Event type token")
    app_p.add_argument("--aggregate", required=True, help="Aggregate ID")
    app_p.add_argument("--data", default="{}", help="Event data JSON string")

    # replay
    rep_p = subparsers.add_parser("replay", help="Replay events from store")
    rep_p.add_argument("--store", required=True, help="Path to event log file")
    rep_p.add_argument("--aggregate", help="Optional aggregate ID filter")
    rep_p.add_argument("--from-seq", type=int, default=0, help="Starting sequence number")

    # snapshot
    snp_p = subparsers.add_parser("snapshot", help="Create a state snapshot")
    snp_p.add_argument("--store", required=True, help="Path to event log file")
    snp_p.add_argument("--aggregate", required=True, help="Aggregate ID")
    snp_p.add_argument("--state", required=True, help="State JSON string")
    snp_p.add_argument("--seq", type=int, default=0, help="Compacted sequence number")

    args = parser.parse_args()
    store = EventStore(args.store)

    if args.action == "append":
        data = json.loads(args.data)
        event = store.append(event_type=args.type, aggregate_id=args.aggregate, data=data)
        print(f"Appended event {event.event_type} (seq={event.seq})")

    elif args.action == "replay":
        events = store.replay(aggregate_id=args.aggregate, from_seq=args.from_seq)
        for ev in events:
            print(f"[{ev.seq}] {ev.event_type} ({ev.aggregate_id}): {json.dumps(ev.data)}")

    elif args.action == "snapshot":
        state = json.loads(args.state)
        snap = store.create_snapshot(aggregate_id=args.aggregate, state=state, up_to_seq=args.seq)
        print(f"Created snapshot for {snap.aggregate_id} at seq {snap.seq}")


if __name__ == "__main__":
    main()
