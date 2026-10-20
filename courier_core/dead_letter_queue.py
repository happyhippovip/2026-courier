"""Dead-Letter Queue (DLQ) Inspector and Auto-Retrier.

Manages failed and poison tasks with exponential backoff schedules,
quarantine isolation, replay capabilities, and audit summaries.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _format_time(dt: datetime) -> str:
    return dt.strftime(TIME_FORMAT)


def _parse_time(ts: str) -> datetime:
    return datetime.strptime(ts, TIME_FORMAT).replace(tzinfo=timezone.utc)


@dataclass
class DLQEntry:
    """Represents a failed or quarantined task in the DLQ."""

    item_id: str
    error_reason: str
    attempts: int
    state: str  # "RETRYABLE" | "QUARANTINED"
    last_failed_at: str
    retry_after: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DLQEntry":
        return cls(
            item_id=data["item_id"],
            error_reason=data["error_reason"],
            attempts=int(data["attempts"]),
            state=data["state"],
            last_failed_at=data["last_failed_at"],
            retry_after=data.get("retry_after"),
        )


class CorruptDLQError(ValueError):
    """Raised when the DLQ state file is corrupt or unreadable: never silently reset."""


class DeadLetterQueue:
    """Core manager for DLQ persistence, state transitions, and retries."""

    def __init__(
        self,
        dlq_path: str = "run/dlq.json",
        max_attempts: int = 3,
        backoff_base_sec: float = 2.0,
    ):
        self.dlq_path = Path(dlq_path)
        self.max_attempts = max_attempts
        self.backoff_base_sec = backoff_base_sec
        self.entries: dict[str, DLQEntry] = {}
        self._load()

    def _load(self):
        if not self.dlq_path.exists():
            return
        if self.dlq_path.is_symlink():
            raise CorruptDLQError(f"{self.dlq_path} is a symlink: refusing insecure load")
        try:
            raw = json.loads(self.dlq_path.read_text(encoding="utf-8"))
            for k, v in raw.items():
                self.entries[k] = DLQEntry.from_dict(v)
        except CorruptDLQError:
            raise
        except (json.JSONDecodeError, UnicodeDecodeError, OSError, KeyError, TypeError) as exc:
            raise CorruptDLQError(f"Corrupt DLQ file at {self.dlq_path}: {exc}") from exc

    def _save(self):
        if self.dlq_path.is_symlink():
            raise CorruptDLQError(f"{self.dlq_path} is a symlink: refusing insecure write")
        self.dlq_path.parent.mkdir(parents=True, exist_ok=True)
        dump = {k: v.to_dict() for k, v in self.entries.items()}
        tmp = self.dlq_path.with_name(self.dlq_path.name + f".tmp.{os.getpid()}")
        payload = json.dumps(dump, indent=2)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(20):
            try:
                os.replace(tmp, self.dlq_path)
                break
            except (PermissionError, OSError):
                if attempt == 19:
                    try:
                        tmp.unlink(missing_ok=True)
                    except Exception:
                        pass
                    raise
                time.sleep(0.01)

    def record_failure(
        self,
        item_id: str,
        error_reason: str,
        attempts: int,
        max_attempts: int | None = None,
        now: datetime | None = None,
        idempotent: bool = True,
    ) -> DLQEntry:
        cur_now = now or _now_utc()
        limit = max_attempts if max_attempts is not None else self.max_attempts

        if idempotent and attempts < limit:
            state = "RETRYABLE"
            backoff_seconds = self.backoff_base_sec ** attempts
            retry_dt = cur_now + timedelta(seconds=backoff_seconds)
            retry_after = _format_time(retry_dt)
        else:
            state = "QUARANTINED"
            retry_after = None

        entry = DLQEntry(
            item_id=item_id,
            error_reason=error_reason,
            attempts=attempts,
            state=state,
            last_failed_at=_format_time(cur_now),
            retry_after=retry_after,
        )
        self.entries[item_id] = entry
        self._save()
        return entry

    def get_retryable_items(self, now: datetime | None = None) -> list[DLQEntry]:
        cur_now = now or _now_utc()
        ready: list[DLQEntry] = []
        for entry in self.entries.values():
            if entry.state == "RETRYABLE" and entry.retry_after:
                try:
                    retry_dt = _parse_time(entry.retry_after)
                    if retry_dt <= cur_now:
                        ready.append(entry)
                except ValueError:
                    continue
        return ready

    def quarantine_item(
        self,
        item_id: str,
        reason: str,
        now: datetime | None = None,
    ) -> DLQEntry:
        cur_now = now or _now_utc()
        existing = self.entries.get(item_id)
        attempts = existing.attempts if existing else 1
        entry = DLQEntry(
            item_id=item_id,
            error_reason=reason,
            attempts=attempts,
            state="QUARANTINED",
            last_failed_at=_format_time(cur_now),
            retry_after=None,
        )
        self.entries[item_id] = entry
        self._save()
        return entry

    def replay_item(
        self,
        item_id: str,
        now: datetime | None = None,
    ) -> DLQEntry:
        cur_now = now or _now_utc()
        existing = self.entries.get(item_id)
        reason = existing.error_reason if existing else "Replayed by operator"
        entry = DLQEntry(
            item_id=item_id,
            error_reason=reason,
            attempts=0,
            state="RETRYABLE",
            last_failed_at=_format_time(cur_now),
            retry_after=_format_time(cur_now),
        )
        self.entries[item_id] = entry
        self._save()
        return entry

    def audit(self) -> dict[str, Any]:
        quarantined = sum(1 for e in self.entries.values() if e.state == "QUARANTINED")
        retryable = sum(1 for e in self.entries.values() if e.state == "RETRYABLE")
        reasons: dict[str, int] = {}
        for e in self.entries.values():
            reasons[e.error_reason] = reasons.get(e.error_reason, 0) + 1

        return {
            "total_entries": len(self.entries),
            "quarantined_count": quarantined,
            "retryable_count": retryable,
            "reasons": reasons,
        }


def record_failure(
    item_id: str,
    error_reason: str,
    attempts: int,
    dlq_path: str = "run/dlq.json",
    max_attempts: int = 3,
    backoff_base_sec: float = 2.0,
    now: datetime | None = None,
) -> DLQEntry:
    dlq = DeadLetterQueue(dlq_path=dlq_path, max_attempts=max_attempts, backoff_base_sec=backoff_base_sec)
    return dlq.record_failure(item_id, error_reason, attempts=attempts, now=now)


def get_retryable_items(
    dlq_path: str = "run/dlq.json",
    now: datetime | None = None,
) -> list[DLQEntry]:
    dlq = DeadLetterQueue(dlq_path=dlq_path)
    return dlq.get_retryable_items(now=now)


def quarantine_item(
    item_id: str,
    reason: str,
    dlq_path: str = "run/dlq.json",
    now: datetime | None = None,
) -> DLQEntry:
    dlq = DeadLetterQueue(dlq_path=dlq_path)
    return dlq.quarantine_item(item_id, reason, now=now)


def replay_item(
    item_id: str,
    dlq_path: str = "run/dlq.json",
    now: datetime | None = None,
) -> DLQEntry:
    dlq = DeadLetterQueue(dlq_path=dlq_path)
    return dlq.replay_item(item_id, now=now)


def audit_quarantine(dlq_path: str = "run/dlq.json") -> dict[str, Any]:
    dlq = DeadLetterQueue(dlq_path=dlq_path)
    return dlq.audit()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dead-Letter Queue CLI manager.")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # record
    p_rec = subparsers.add_parser("record")
    p_rec.add_argument("--item", required=True)
    p_rec.add_argument("--reason", required=True)
    p_rec.add_argument("--attempts", type=int, default=1)
    p_rec.add_argument("--max-attempts", type=int, default=3)
    p_rec.add_argument("--dlq-file", default="run/dlq.json")

    # quarantine
    p_quar = subparsers.add_parser("quarantine")
    p_quar.add_argument("--item", required=True)
    p_quar.add_argument("--reason", required=True)
    p_quar.add_argument("--dlq-file", default="run/dlq.json")

    # replay
    p_rep = subparsers.add_parser("replay")
    p_rep.add_argument("--item", required=True)
    p_rep.add_argument("--dlq-file", default="run/dlq.json")

    # retryable
    p_ret = subparsers.add_parser("get-retryable")
    p_ret.add_argument("--dlq-file", default="run/dlq.json")

    # audit
    p_aud = subparsers.add_parser("audit")
    p_aud.add_argument("--dlq-file", default="run/dlq.json")

    args = parser.parse_args(argv)

    if args.subcommand == "record":
        dlq = DeadLetterQueue(dlq_path=args.dlq_file, max_attempts=args.max_attempts)
        entry = dlq.record_failure(args.item, args.reason, attempts=args.attempts)
        print(json.dumps({"status": "RECORDED", "entry": entry.to_dict()}))
    elif args.subcommand == "quarantine":
        dlq = DeadLetterQueue(dlq_path=args.dlq_file)
        entry = dlq.quarantine_item(args.item, args.reason)
        print(json.dumps({"status": "QUARANTINED", "entry": entry.to_dict()}))
    elif args.subcommand == "replay":
        dlq = DeadLetterQueue(dlq_path=args.dlq_file)
        entry = dlq.replay_item(args.item)
        print(json.dumps({"status": "REPLAYED", "entry": entry.to_dict()}))
    elif args.subcommand == "get-retryable":
        dlq = DeadLetterQueue(dlq_path=args.dlq_file)
        items = dlq.get_retryable_items()
        print(json.dumps({"status": "RETRYABLE", "items": [i.to_dict() for i in items]}))
    elif args.subcommand == "audit":
        dlq = DeadLetterQueue(dlq_path=args.dlq_file)
        res = dlq.audit()
        print(json.dumps({"status": "AUDITED", "summary": res}))

    return 0


if __name__ == "__main__":
    sys.exit(main())
