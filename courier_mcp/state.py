"""Fail-closed view of one Courier home for the MCP server.

Real mode does not parse the bridge file itself. It calls
``courier_core.receipt_read_model.ReceiptReadModel``, which reads
``<state_dir>/ledger_bridge_state.json`` and ``<state_dir>/courier.db``.
Demo mode still parses an in-memory synthetic document.

A missing bridge is ``ABSENT`` (empty). A symlink, a file the read model
rejects, or a receipt the MCP server will not show (unknown status/reason,
unparseable timestamp, non-printable or over-long text) is ``UNREADABLE``
and yields no missions. Callers never get an exception or a filesystem path.
Nothing here writes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from courier_core.receipt_read_model import (
    BRIDGE_NAME,
    KNOWN_STATUSES,
    MAX_FILE_BYTES,
    RESULTS_NAME,
    ReceiptReadModel,
)

STATE_NAME = BRIDGE_NAME
MAX_STATE_BYTES = MAX_FILE_BYTES
MAX_MISSIONS = 2000
MAX_TEXT = 200
STALE_AFTER_SECONDS = 15 * 60
CLOCK_SKEW_SECONDS = 60
STATUSES = ("POSTED", "FINAL_DONE", "BLOCKED", "ERROR")
REASONS = ("CONTROLLER_BLOCKED", "FAILED", "CANCELLED", "GOAL_PAIR", "GOAL_TOKEN")
OPTIONAL_FIELDS = (
    "accepted_result_id",
    "claim_event_id",
    "evidence_ref",
    "goal_id",
    "reason",
    "status",
    "updated_at",
)
PUBLIC_FIELDS = ("mission_id", "task_id", "status", "reason", "goal_id", "updated_at",
                 "accepted_result_id", "claim_event_id", "evidence_ref")


class Snapshot:
    """One read of the state. ``source`` is ABSENT, OK, UNREADABLE or DEMO."""

    def __init__(self, source: str, missions: list[dict], mtime: float | None = None,
                 model_receipts: list[dict] | None = None, model_summary: dict | None = None):
        self.source = source
        self.missions = missions
        self.mtime = mtime
        # Real mode only. These are the read model's own objects; demo leaves them unset.
        self.model_receipts = model_receipts
        self.model_summary = model_summary

    @property
    def readable(self) -> bool:
        return self.source != "UNREADABLE"


def read_state_dir(state_dir) -> Snapshot:
    """One real-mode read. File bytes come only from ``ReceiptReadModel``."""
    root = Path(state_dir)
    if _refuses_symlink(root):
        return _unreadable()
    model = ReceiptReadModel(root)
    listed = model.list_receipts()
    summary = model.summary()
    if not listed["readable"] or not summary["readable"]:
        return _unreadable(summary)
    if listed["bridge"] != "OK":
        return Snapshot("ABSENT", [], model_receipts=[], model_summary=summary)
    rows = []
    for receipt in listed["receipts"]:
        row = _row_from_receipt(receipt)
        if row is None:
            return _unreadable(_zero_summary(summary.get("results")))
        rows.append(row)
    return Snapshot("OK", rows, _mtime(root / STATE_NAME),
                    model_receipts=list(listed["receipts"]), model_summary=summary)


def _refuses_symlink(root: Path) -> bool:
    for name in (STATE_NAME, RESULTS_NAME):
        try:
            if (root / name).is_symlink():
                return True
        except OSError:
            return True
    return False


def _mtime(path: Path):
    try:
        if path.is_symlink() or not path.is_file():
            return None
        return path.stat().st_mtime
    except OSError:
        return None


def _unreadable(summary: dict | None = None) -> Snapshot:
    return Snapshot("UNREADABLE", [], model_receipts=[], model_summary=summary or _zero_summary(None))


def _zero_summary(results_state) -> dict:
    return {
        "readable": False,
        "bridge": "UNREADABLE",
        "results": results_state if results_state in ("OK", "ABSENT", "UNREADABLE") else "UNREADABLE",
        "counts": {name: 0 for name in (*KNOWN_STATUSES, "UNSET")},
        "total": 0,
        "last_updated": None,
    }


def _row_from_receipt(receipt) -> dict | None:
    if not isinstance(receipt, dict):
        return None
    mission_id = receipt.get("mission_id")
    task_id = receipt.get("task_id")
    if not _text(mission_id) or not _text(task_id):
        return None
    row = {"mission_id": mission_id, "task_id": task_id}
    for name in OPTIONAL_FIELDS:
        value = receipt.get(name)
        if value is None:
            row[name] = None
            continue
        if not _text(value):
            return None
        row[name] = value
    if row["status"] is not None and row["status"] not in STATUSES:
        return None
    if row["reason"] is not None and row["reason"] not in REASONS:
        return None
    if row["updated_at"] is not None and parse_time(row["updated_at"]) is None:
        return None
    return row


def parse_document(document, source: str = "OK", mtime: float | None = None) -> Snapshot:
    missions = _missions(document)
    if missions is None:
        return Snapshot("UNREADABLE", [], mtime)
    return Snapshot(source, missions, mtime)


def _missions(document):
    if not isinstance(document, dict) or set(document) != {"missions"}:
        return None
    raw = document["missions"]
    rows = []
    if isinstance(raw, dict):
        items = list(raw.items())
    elif isinstance(raw, list):
        items = []
        for mapping in raw:
            if not isinstance(mapping, dict):
                return None
            items.append((mapping.get("mission_id"), mapping))
    else:
        return None
    if len(items) > MAX_MISSIONS:
        return None
    seen = set()
    for mission_id, mapping in items:
        if not _text(mission_id) or not isinstance(mapping, dict):
            return None
        if "mission_id" in mapping and mapping["mission_id"] != mission_id:
            return None
        task_id = mapping.get("task_id")
        if not _text(task_id) or task_id in seen:
            return None
        seen.add(task_id)
        row = {"mission_id": mission_id, "task_id": task_id}
        for name in OPTIONAL_FIELDS:
            value = mapping.get(name)
            if value is None:
                row[name] = None
                continue
            if not _text(value):
                return None
            row[name] = value
        if row["status"] is not None and row["status"] not in STATUSES:
            return None
        if row["reason"] is not None and row["reason"] not in REASONS:
            return None
        if row["updated_at"] is not None and parse_time(row["updated_at"]) is None:
            return None
        rows.append(row)
    rows.sort(key=lambda item: (item["updated_at"] or "", item["mission_id"]), reverse=True)
    return rows


def _text(value) -> bool:
    return isinstance(value, str) and 0 < len(value) <= MAX_TEXT and value.isprintable()


def parse_time(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        moment = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    return moment.astimezone(timezone.utc)


def effective_status(row: dict) -> str:
    """Older files lack ``status``: a result means FINAL_DONE, otherwise POSTED."""
    if row["status"] is not None:
        return row["status"]
    return "FINAL_DONE" if row["accepted_result_id"] else "POSTED"


def automation_card(snapshot: Snapshot, now: datetime) -> dict:
    """Same precedence as the hub card: ERROR > BLOCKED > RUNNING/STALE > IDLE."""
    if snapshot.source == "UNREADABLE":
        return _card("ATTENTION", "Needs attention", "The automation record could not be read.", reason="UNREADABLE")
    if snapshot.source == "ABSENT":
        return _card("NOT_CONFIGURED", "Not set up", "Courier has no automation record here.")
    rows = snapshot.missions
    ages = []
    for row in rows:
        moment = parse_time(row["updated_at"]) if row["updated_at"] else None
        if moment is None and snapshot.mtime is not None:
            moment = datetime.fromtimestamp(snapshot.mtime, tz=timezone.utc)
        if moment is None:
            ages.append(None)
            continue
        age = (now - moment).total_seconds()
        if age < -CLOCK_SKEW_SECONDS:
            return _card("ATTENTION", "Needs attention", "The automation record has a time this server does not trust.",
                         reason="CLOCK")
        ages.append(max(0, int(age)))
    statuses = [effective_status(row) for row in rows]
    errors = [row for row, status in zip(rows, statuses) if status == "ERROR"]
    if errors:
        return _card("ATTENTION", "Needs attention", f"{len(errors)} mission(s) ended in error.", reason="ERROR",
                     reason_codes=sorted({row["reason"] for row in errors if row["reason"]}))
    blocked = [row for row, status in zip(rows, statuses) if status == "BLOCKED"]
    if blocked:
        return _card("BLOCKED", "Blocked", f"{len(blocked)} mission(s) are blocked.",
                     reason_codes=sorted({row["reason"] for row in blocked if row["reason"]}))
    posted_ages = [age for age, status in zip(ages, statuses) if status == "POSTED"]
    if posted_ages:
        if any(age is None for age in posted_ages):
            return _card("ATTENTION", "Needs attention", "A running mission has no usable time.", reason="CLOCK")
        oldest = max(posted_ages)
        if oldest > STALE_AFTER_SECONDS:
            return _card("ATTENTION", "Needs attention",
                         "The automation record is too old to say whether work is still moving.", reason="STALE",
                         age_seconds=oldest)
        return _card("RUNNING", "Running", f"{len(posted_ages)} mission(s) in flight.", in_flight=len(posted_ages),
                     age_seconds=oldest)
    return _card("IDLE", "Idle", "No missions are in flight.", in_flight=0)


def _card(state, label, detail, reason=None, reason_codes=None, in_flight=None, age_seconds=None) -> dict:
    return {
        "state": state,
        "label": label,
        "detail": detail,
        "reason": reason,
        "reason_codes": list(reason_codes or []),
        "in_flight": in_flight,
        "age_seconds": age_seconds,
    }


def public_row(row: dict) -> dict:
    out = {name: row.get(name) for name in PUBLIC_FIELDS}
    out["status"] = effective_status(row)
    return out
