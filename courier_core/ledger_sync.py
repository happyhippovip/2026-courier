"""Dual-Ledger Bridge and State Reconciler.

Synchronizes event ledgers across nodes and boundaries with idempotency,
conflict detection, sequence monotonicity, and watermark tracking.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


def _canonical_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


@dataclass
class SyncResult:
    """Outcome of a ledger replication pass."""

    synced_count: int
    skipped_count: int
    last_event_id: str | None = None


class LedgerBridge:
    """Bridges events from source ledger to target ledger idempotently."""

    def __init__(
        self,
        source_path: str,
        target_path: str,
        watermark_path: str | None = None,
    ):
        self.source_path = Path(source_path)
        self.target_path = Path(target_path)
        self.watermark_path = Path(watermark_path) if watermark_path else None

    def _read_ledger(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    events.append(json.loads(stripped))
        return events

    def _read_watermark(self) -> str | None:
        if self.watermark_path and self.watermark_path.exists():
            return self.watermark_path.read_text(encoding="utf-8").strip() or None
        return None

    def _write_watermark(self, event_id: str):
        if self.watermark_path:
            self.watermark_path.parent.mkdir(parents=True, exist_ok=True)
            self.watermark_path.write_text(event_id, encoding="utf-8")

    @staticmethod
    def _derive_event_id(ev: dict[str, Any]) -> str | None:
        eid = ev.get("event_id")
        if isinstance(eid, str) and eid.strip():
            return eid.strip()
        # Support canonical work_queue_ledger.jsonl events (type + item_id + at/created_at)
        ev_type = ev.get("type") or ev.get("event_type")
        item_id = ev.get("item_id") or ev.get("task_id")
        at_ts = ev.get("at") or ev.get("created_at") or ev.get("ts_utc")
        if ev_type and item_id and at_ts:
            digest = hashlib.sha256(_canonical_json(ev).encode("utf-8")).hexdigest()[:24]
            return f"wq-{item_id}-{digest}"
        return None

    def sync_forward(self) -> SyncResult:
        source_events = self._read_ledger(self.source_path)
        target_events = self._read_ledger(self.target_path)

        # Build index of existing target events by event_id
        target_index: dict[str, str] = {}
        for ev in target_events:
            eid = self._derive_event_id(ev)
            if eid:
                ev_norm = {**ev, "event_id": eid} if "event_id" not in ev else ev
                target_index[eid] = _canonical_json(ev_norm)

        watermark = self._read_watermark()
        source_eids = {self._derive_event_id(ev) for ev in source_events}
        # If watermark was compacted out of source_events, fall back to target_index deduplication
        reached_watermark = (watermark is None) or (watermark not in source_eids)

        synced_count = 0
        skipped_count = 0
        last_event_id = watermark

        new_events_to_append: list[dict[str, Any]] = []

        for ev in source_events:
            eid = self._derive_event_id(ev)
            if not eid:
                continue

            ev_norm = {**ev, "event_id": eid} if "event_id" not in ev else ev
            canon = _canonical_json(ev_norm)

            # Check if event already exists in target
            if eid in target_index:
                if target_index[eid] != canon:
                    raise ValueError(f"Ledger conflict or tamper detected for event '{eid}'")
                skipped_count += 1
                if watermark and eid == watermark:
                    reached_watermark = True
                continue

            if not reached_watermark:
                if eid == watermark:
                    reached_watermark = True
                continue

            new_events_to_append.append(ev_norm)
            target_index[eid] = canon
            synced_count += 1
            last_event_id = eid

        if new_events_to_append:
            self.target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.target_path, "a", encoding="utf-8") as f:
                for ev in new_events_to_append:
                    f.write(json.dumps(ev) + "\n")

        if last_event_id:
            self._write_watermark(last_event_id)

        return SyncResult(
            synced_count=synced_count,
            skipped_count=skipped_count,
            last_event_id=last_event_id,
        )


def sync_ledgers(
    source_path: str,
    target_path: str,
    watermark_path: str | None = None,
) -> SyncResult:
    """Convenience functional wrapper to sync source to target."""
    bridge = LedgerBridge(
        source_path=source_path,
        target_path=target_path,
        watermark_path=watermark_path,
    )
    return bridge.sync_forward()


def reconcile_bidirectional(path_a: str, path_b: str) -> tuple[SyncResult, SyncResult]:
    """Reconcile two ledgers bidirectionally so both end up in parity."""
    # First sync A -> B
    res_a_to_b = sync_ledgers(path_a, path_b)
    # Then sync B -> A
    res_b_to_a = sync_ledgers(path_b, path_a)
    return res_a_to_b, res_b_to_a


def main(argv: Sequence[str] | None = None) -> int:
    """CLI Entrypoint for Dual-Ledger Sync."""
    parser = argparse.ArgumentParser(description="Synchronize ledger events across files.")
    parser.add_argument("--source", required=True, help="Path to source ledger JSONL")
    parser.add_argument("--target", required=True, help="Path to target ledger JSONL")
    parser.add_argument("--watermark", help="Optional path to persistent watermark file")
    parser.add_argument("--bidirectional", action="store_true", help="Reconcile in both directions")

    args = parser.parse_args(argv)

    if args.bidirectional:
        res_a, res_b = reconcile_bidirectional(args.source, args.target)
        print(json.dumps({
            "status": "RECONCILED",
            "source_to_target": {"synced": res_a.synced_count, "skipped": res_a.skipped_count},
            "target_to_source": {"synced": res_b.synced_count, "skipped": res_b.skipped_count},
        }))
    else:
        res = sync_ledgers(args.source, args.target, watermark_path=args.watermark)
        print(json.dumps({
            "status": "SYNCED",
            "synced_count": res.synced_count,
            "skipped_count": res.skipped_count,
            "last_event_id": res.last_event_id,
        }))

    return 0


if __name__ == "__main__":
    sys.exit(main())
