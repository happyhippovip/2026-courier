"""Durable worker outbox drain coordinator with fail-closed delivery idempotency.

Lane L3. Inspects and flushes durable outbox files (<home>/outbox/*.json).
Deliveries are single-attempt and non-mutating on error (payload stays in outbox
for subsequent flush). Corrupt files are quarantined safely to prevent loop crashes.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass
class OutboxDrainReport:
    drained_count: int
    remaining_count: int
    corrupt_count: int
    success: bool
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def drain_outbox(
    home_path: str | Path,
    deliver_fn: Optional[Callable[[dict[str, Any]], bool]] = None,
    max_items: int = 32,
    dry_run: bool = False,
) -> OutboxDrainReport:
    home = Path(home_path)
    outbox_dir = home / "outbox"

    if not outbox_dir.exists() or not outbox_dir.is_dir():
        return OutboxDrainReport(
            drained_count=0,
            remaining_count=0,
            corrupt_count=0,
            success=True,
        )

    # Collect valid json files, skip subdirectories (e.g. corrupt/)
    files = sorted(
        [p for p in outbox_dir.iterdir() if p.is_file() and p.suffix.lower() == ".json"]
    )

    drained_count = 0
    corrupt_count = 0
    errors: list[str] = []

    to_process = files[:max_items]

    for p in to_process:
        try:
            with open(p, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as exc:
            corrupt_count += 1
            errors.append(f"corrupt_outbox_file: {p.name}: {exc}")
            if not dry_run:
                try:
                    corrupt_dir = outbox_dir / "corrupt"
                    corrupt_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(p), str(corrupt_dir / p.name))
                except Exception as move_exc:
                    errors.append(f"failed to quarantine {p.name}: {move_exc}")
            continue

        if dry_run:
            continue

        if deliver_fn is None:
            errors.append(f"no_delivery_handler: {p.name}")
            continue

        try:
            delivered = deliver_fn(payload)
        except Exception as exc:
            delivered = False
            errors.append(f"delivery_exception: {p.name}: {exc}")

        if delivered:
            try:
                p.unlink(missing_ok=True)
                drained_count += 1
            except Exception as del_exc:
                errors.append(f"failed to remove {p.name}: {del_exc}")

    # Count remaining json files
    current_files = [p for p in outbox_dir.iterdir() if p.is_file() and p.suffix.lower() == ".json"]
    remaining_count = len(current_files)

    return OutboxDrainReport(
        drained_count=drained_count,
        remaining_count=remaining_count,
        corrupt_count=corrupt_count,
        success=len(errors) == 0,
        errors=errors,
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="courier_core.outbox_drain",
        description="Drain durable worker outbox payloads.",
    )
    parser.add_argument("home_path", help="Path to home directory")
    parser.add_argument("--dry-run", action="store_true", help="Inspect outbox without delivering or removing")
    parser.add_argument("--deliver-dir", default=None, help="Directory to write delivered payloads into")
    parser.add_argument("--max-items", type=int, default=32, help="Maximum number of payloads to process")
    args = parser.parse_args(argv)

    deliver_fn: Optional[Callable[[dict[str, Any]], bool]] = None
    if args.deliver_dir:
        target_dir = Path(args.deliver_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        def _file_deliver(payload: dict[str, Any]) -> bool:
            dispatch_id = str(payload.get("dispatch_id") or "unknown")
            safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in dispatch_id)
            dest = target_dir / f"{safe_name}.json"
            dest.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            return True

        deliver_fn = _file_deliver

    report = drain_outbox(args.home_path, deliver_fn=deliver_fn, max_items=args.max_items, dry_run=args.dry_run)
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.success else 1


if __name__ == "__main__":
    sys.exit(main())
