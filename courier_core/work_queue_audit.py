"""Audit tool for the canonical ledger-backed work queue.

Validates append-only JSONL ledgers for structural integrity, chronological
order, state-machine transitions, lease validities, idempotency, and
mutual-exclusion of scope-overlapping tasks across time.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from courier_core.work_queue import (
    DEFAULT_ITEMS,
    MAX_LEDGER_BYTES,
    MAX_TTL_SECONDS,
    _TIME,
    _TOKEN,
    _parse_time,
    _stamp,
    scopes_overlap,
)


@dataclass
class AuditViolation:
    line_number: Optional[int]
    code: str
    message: str
    event: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditReport:
    valid: bool
    total_lines: int
    events_count: int
    items_count: int
    active_leases_count: int
    completed_count: int
    violations: List[AuditViolation]
    items: Dict[str, Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "total_lines": self.total_lines,
            "events_count": self.events_count,
            "items_count": self.items_count,
            "active_leases_count": self.active_leases_count,
            "completed_count": self.completed_count,
            "violations": [v.to_dict() for v in self.violations],
            "items": self.items,
        }

    def summary(self) -> str:
        status_word = "PASSED" if self.valid else "FAILED"
        lines = [
            f"WorkQueue Audit: {status_word}",
            f"  Events evaluated: {self.events_count} (across {self.total_lines} lines)",
            f"  Items tracked:    {self.items_count} (completed: {self.completed_count}, active leases: {self.active_leases_count})",
            f"  Violations found: {len(self.violations)}",
        ]
        if self.violations:
            lines.append("\nViolations:")
            for v in self.violations:
                loc = f"Line {v.line_number}" if v.line_number is not None else "Global"
                lines.append(f"  [{loc}] {v.code}: {v.message}")
        return "\n".join(lines)


def load_catalog_scopes(items_dir: Path) -> Dict[str, List[str]]:
    """Loads files_scope for each known work item in the catalog."""
    scopes: Dict[str, List[str]] = {}
    if not items_dir.exists() or not items_dir.is_dir():
        return scopes
    for child in items_dir.iterdir():
        if child.is_file() and child.suffix == ".json":
            try:
                data = json.loads(child.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "id" in data and "files_scope" in data:
                    item_id = str(data["id"])
                    scope = data["files_scope"]
                    if isinstance(scope, list):
                        scopes[item_id] = [str(p) for p in scope]
            except Exception:
                continue
    return scopes


class WorkQueueAuditor:
    def __init__(self, ledger_path: Path | str, items_dir: Path | str | None = None):
        self.ledger_path = Path(ledger_path)
        self.items_dir = Path(items_dir) if items_dir is not None else None
        self.catalog_scopes: Dict[str, List[str]] = {}
        if self.items_dir is not None:
            self.catalog_scopes = load_catalog_scopes(self.items_dir)

    def audit(self) -> AuditReport:
        violations: List[AuditViolation] = []
        path = self.ledger_path

        if not path.exists():
            return AuditReport(
                valid=True,
                total_lines=0,
                events_count=0,
                items_count=0,
                active_leases_count=0,
                completed_count=0,
                violations=[],
                items={},
            )

        if path.is_symlink():
            violations.append(
                AuditViolation(
                    line_number=None,
                    code="SYMLINK_DISALLOWED",
                    message="Ledger file must not be a symbolic link",
                )
            )
            return AuditReport(False, 0, 0, 0, 0, 0, violations, {})

        if not path.is_file():
            violations.append(
                AuditViolation(
                    line_number=None,
                    code="NOT_A_FILE",
                    message="Ledger path is not a regular file",
                )
            )
            return AuditReport(False, 0, 0, 0, 0, 0, violations, {})

        try:
            size = path.stat().st_size
        except OSError as exc:
            violations.append(
                AuditViolation(line_number=None, code="UNREADABLE", message=f"Failed to stat ledger: {exc}")
            )
            return AuditReport(False, 0, 0, 0, 0, 0, violations, {})

        if size > MAX_LEDGER_BYTES:
            violations.append(
                AuditViolation(
                    line_number=None,
                    code="LEDGER_TOO_LARGE",
                    message=f"Ledger byte size {size} exceeds maximum {MAX_LEDGER_BYTES}",
                )
            )
            return AuditReport(False, 0, 0, 0, 0, 0, violations, {})

        try:
            raw = path.read_bytes()
        except OSError as exc:
            violations.append(
                AuditViolation(line_number=None, code="UNREADABLE", message=f"Failed to read ledger: {exc}")
            )
            return AuditReport(False, 0, 0, 0, 0, 0, violations, {})

        items: Dict[str, Dict[str, Any]] = {}
        prev_created_at: Optional[datetime] = None
        total_lines = 0
        events_count = 0

        lines = raw.splitlines()
        for idx, line_bytes in enumerate(lines, start=1):
            total_lines += 1
            line_str = line_bytes.strip()
            if not line_str:
                continue

            try:
                line_text = line_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                violations.append(
                    AuditViolation(
                        line_number=idx,
                        code="UTF8_DECODE_ERROR",
                        message=f"Line is not valid UTF-8: {exc}",
                    )
                )
                continue

            try:
                event = json.loads(line_text)
            except json.JSONDecodeError as exc:
                violations.append(
                    AuditViolation(
                        line_number=idx,
                        code="JSON_SYNTAX_ERROR",
                        message=f"Malformed JSON: {exc}",
                    )
                )
                continue

            if not isinstance(event, dict):
                violations.append(
                    AuditViolation(
                        line_number=idx,
                        code="MALFORMED_EVENT",
                        message="Event record must be a JSON object",
                        event=None,
                    )
                )
                continue

            events_count += 1
            kind = event.get("type")
            item_id = event.get("item_id")
            holder = event.get("holder")
            created_at_raw = event.get("created_at")

            # Validate basic envelope tokens
            if kind not in ("CLAIM", "RENEW", "RELEASE"):
                violations.append(
                    AuditViolation(
                        line_number=idx,
                        code="UNKNOWN_EVENT_TYPE",
                        message=f"Event type '{kind}' is unknown",
                        event=event,
                    )
                )
                continue

            if not isinstance(item_id, str) or _TOKEN.fullmatch(item_id) is None or len(item_id) > 64:
                violations.append(
                    AuditViolation(
                        line_number=idx,
                        code="INVALID_ITEM_ID",
                        message=f"Invalid item_id token: {item_id!r}",
                        event=event,
                    )
                )
                continue

            if not isinstance(holder, str) or _TOKEN.fullmatch(holder) is None or len(holder) > 64:
                violations.append(
                    AuditViolation(
                        line_number=idx,
                        code="INVALID_HOLDER",
                        message=f"Invalid holder token: {holder!r}",
                        event=event,
                    )
                )
                continue

            created_at = _parse_time(created_at_raw)
            if created_at is None:
                violations.append(
                    AuditViolation(
                        line_number=idx,
                        code="INVALID_TIMESTAMP",
                        message=f"created_at '{created_at_raw}' is not valid ISO 8601 UTC timestamp",
                        event=event,
                    )
                )
                continue

            # Chronology check
            if prev_created_at is not None and created_at < prev_created_at:
                violations.append(
                    AuditViolation(
                        line_number=idx,
                        code="TIME_TRAVEL",
                        message=f"Event created_at {created_at_raw} is earlier than previous event {_stamp(prev_created_at)}",
                        event=event,
                    )
                )
            prev_created_at = created_at

            # State transition analysis per item
            state = items.setdefault(
                item_id,
                {
                    "item_id": item_id,
                    "status": "UNCLAIMED",
                    "lease": None,
                    "result": None,
                    "history": [],
                },
            )
            state["history"].append(event)

            if kind == "CLAIM":
                host = event.get("host")
                expires_at_raw = event.get("expires_at")

                if not isinstance(host, str) or _TOKEN.fullmatch(host) is None or len(host) > 64:
                    violations.append(
                        AuditViolation(
                            line_number=idx,
                            code="INVALID_HOST",
                            message=f"Invalid host token: {host!r}",
                            event=event,
                        )
                    )
                    continue

                expires_at = _parse_time(expires_at_raw)
                if expires_at is None:
                    violations.append(
                        AuditViolation(
                            line_number=idx,
                            code="INVALID_TIMESTAMP",
                            message=f"expires_at '{expires_at_raw}' is not valid ISO 8601 UTC timestamp",
                            event=event,
                        )
                    )
                    continue

                if expires_at <= created_at:
                    violations.append(
                        AuditViolation(
                            line_number=idx,
                            code="EXPIRES_IN_PAST",
                            message=f"expires_at {expires_at_raw} must be strictly greater than created_at {created_at_raw}",
                            event=event,
                        )
                    )

                ttl = (expires_at - created_at).total_seconds()
                if ttl > MAX_TTL_SECONDS:
                    violations.append(
                        AuditViolation(
                            line_number=idx,
                            code="TTL_OUT_OF_BOUNDS",
                            message=f"TTL of {ttl}s exceeds MAX_TTL_SECONDS ({MAX_TTL_SECONDS})",
                            event=event,
                        )
                    )

                # State machine check
                if state["status"] == "DONE":
                    violations.append(
                        AuditViolation(
                            line_number=idx,
                            code="ALREADY_DONE",
                            message=f"Cannot claim item '{item_id}' which is already released and DONE",
                            event=event,
                        )
                    )
                elif state["status"] == "CLAIMED":
                    curr_lease = state["lease"]
                    curr_expires = _parse_time(curr_lease.get("expires_at"))
                    if curr_expires is not None and created_at <= curr_expires:
                        # Active lease exists
                        if curr_lease.get("holder") == holder and curr_lease.get("expires_at") == expires_at_raw:
                            # Idempotent replay of same claim
                            pass
                        else:
                            violations.append(
                                AuditViolation(
                                    line_number=idx,
                                    code="DUPLICATE_CLAIM",
                                    message=f"Item '{item_id}' is actively claimed by '{curr_lease.get('holder')}' until {curr_lease.get('expires_at')}",
                                    event=event,
                                )
                            )
                    else:
                        # Prior lease expired, clean takeover
                        state["status"] = "CLAIMED"
                        state["lease"] = {"holder": holder, "host": host, "expires_at": expires_at_raw}
                else:
                    state["status"] = "CLAIMED"
                    state["lease"] = {"holder": holder, "host": host, "expires_at": expires_at_raw}

                # Scope overlap check against other concurrently active items
                if self.catalog_scopes and item_id in self.catalog_scopes:
                    item_scope = self.catalog_scopes[item_id]
                    for other_id, other_state in items.items():
                        if other_id == item_id or other_state["status"] != "CLAIMED":
                            continue
                        other_lease = other_state.get("lease")
                        if not other_lease:
                            continue
                        other_exp = _parse_time(other_lease.get("expires_at"))
                        if other_exp is not None and created_at <= other_exp:
                            if other_id in self.catalog_scopes:
                                if scopes_overlap(item_scope, self.catalog_scopes[other_id]):
                                    violations.append(
                                        AuditViolation(
                                            line_number=idx,
                                            code="CONCURRENT_SCOPE_CONFLICT",
                                            message=f"Item '{item_id}' was claimed while overlapping item '{other_id}' is actively leased",
                                            event=event,
                                        )
                                    )

            elif kind == "RENEW":
                expires_at_raw = event.get("expires_at")
                expires_at = _parse_time(expires_at_raw)
                if expires_at is None:
                    violations.append(
                        AuditViolation(
                            line_number=idx,
                            code="INVALID_TIMESTAMP",
                            message=f"expires_at '{expires_at_raw}' is not valid ISO 8601 UTC timestamp",
                            event=event,
                        )
                    )
                    continue

                if expires_at <= created_at:
                    violations.append(
                        AuditViolation(
                            line_number=idx,
                            code="EXPIRES_IN_PAST",
                            message=f"expires_at {expires_at_raw} must be strictly greater than created_at {created_at_raw}",
                            event=event,
                        )
                    )

                if state["status"] == "DONE":
                    violations.append(
                        AuditViolation(
                            line_number=idx,
                            code="ALREADY_DONE",
                            message=f"Cannot renew item '{item_id}' which is already released and DONE",
                            event=event,
                        )
                    )
                elif state["status"] != "CLAIMED" or not state.get("lease"):
                    violations.append(
                        AuditViolation(
                            line_number=idx,
                            code="NOT_CLAIMED",
                            message=f"Cannot renew item '{item_id}' which is not currently claimed",
                            event=event,
                        )
                    )
                else:
                    curr_lease = state["lease"]
                    if curr_lease.get("holder") != holder:
                        violations.append(
                            AuditViolation(
                                line_number=idx,
                                code="NOT_HOLDER",
                                message=f"Holder '{holder}' cannot renew item held by '{curr_lease.get('holder')}'",
                                event=event,
                            )
                        )
                    else:
                        curr_exp = _parse_time(curr_lease.get("expires_at"))
                        if curr_exp is not None and created_at > curr_exp:
                            violations.append(
                                AuditViolation(
                                    line_number=idx,
                                    code="LEASE_EXPIRED",
                                    message=f"Lease for '{item_id}' expired at {_stamp(curr_exp)} before renewal at {_stamp(created_at)}",
                                    event=event,
                                )
                            )
                        else:
                            curr_lease["expires_at"] = expires_at_raw

            elif kind == "RELEASE":
                result = event.get("result")
                if not isinstance(result, str) or not result.strip() or len(result) > 200 or any(ch in result for ch in "\n\r"):
                    violations.append(
                        AuditViolation(
                            line_number=idx,
                            code="INVALID_RESULT",
                            message="Release result must be single-line non-empty string up to 200 characters",
                            event=event,
                        )
                    )
                    continue

                if state["status"] == "DONE":
                    if state.get("released_by") == holder and state.get("result") == result.strip():
                        # Idempotent replay
                        pass
                    else:
                        violations.append(
                            AuditViolation(
                                line_number=idx,
                                code="CONFLICTING_RELEASE",
                                message=f"Item '{item_id}' was already released with result {state.get('result')!r}",
                                event=event,
                            )
                        )
                elif state["status"] != "CLAIMED" or not state.get("lease"):
                    violations.append(
                        AuditViolation(
                            line_number=idx,
                            code="NOT_CLAIMED",
                            message=f"Cannot release item '{item_id}' which is not currently claimed",
                            event=event,
                        )
                    )
                else:
                    curr_lease = state["lease"]
                    if curr_lease.get("holder") != holder:
                        violations.append(
                            AuditViolation(
                                line_number=idx,
                                code="NOT_HOLDER",
                                message=f"Holder '{holder}' cannot release item held by '{curr_lease.get('holder')}'",
                                event=event,
                            )
                        )
                    else:
                        state["status"] = "DONE"
                        state["lease"] = None
                        state["result"] = result.strip()
                        state["released_by"] = holder

        # Calculate statistics
        active_leases = 0
        completed = 0
        for s in items.values():
            if s["status"] == "DONE":
                completed += 1
            elif s["status"] == "CLAIMED":
                active_leases += 1

        is_valid = len(violations) == 0

        return AuditReport(
            valid=is_valid,
            total_lines=total_lines,
            events_count=events_count,
            items_count=len(items),
            active_leases_count=active_leases,
            completed_count=completed,
            violations=violations,
            items=items,
        )


def audit_work_queue_ledger(
    ledger_path: Path | str,
    items_dir: Path | str | None = None,
) -> AuditReport:
    """Convenience function to audit a work queue ledger."""
    auditor = WorkQueueAuditor(ledger_path=ledger_path, items_dir=items_dir)
    return auditor.audit()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m courier_core.work_queue_audit",
        description="Audit one work-queue ledger for consistency.",
    )
    parser.add_argument("--ledger", required=True, help="Path to work_queue_ledger.jsonl")
    parser.add_argument("--items", default=None, help="Path to registries/work_items catalog")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Output audit report as JSON")
    args = parser.parse_args(argv)

    ledger_path = Path(args.ledger).expanduser()
    items_dir = Path(args.items).expanduser() if args.items else DEFAULT_ITEMS

    report = audit_work_queue_ledger(ledger_path=ledger_path, items_dir=items_dir)

    if args.as_json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        if report.valid:
            print(report.summary())
        else:
            print(report.summary(), file=sys.stderr)

    return 0 if report.valid else 2


if __name__ == "__main__":
    sys.exit(main())
