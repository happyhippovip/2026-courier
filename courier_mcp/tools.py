"""Read-only MCP tools. Every tool re-reads the source; none of them write."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from . import __version__
from .demo import demo_snapshot
from .state import STATUSES, Snapshot, automation_card, effective_status, public_row, read_state_dir

MAX_LIMIT = 100
DEFAULT_LIMIT = 25
MAX_RESULT_BYTES = 256 * 1024

ABOUT = {
    "name": "Courier",
    "tagline": "Ideas travel further.",
    "summary": (
        "Courier coordinates AI agents on real work. A mission is posted, claimed, "
        "worked, checked and recorded. Status and receipts come only from recorded, "
        "verified results, not from what an agent says about itself."
    ),
    "this_server": (
        "Read-only view: automation status, missions and receipts. "
        "It cannot start, change or delete anything."
    ),
}

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
_STATUS_FILTER = {"type": "string", "enum": list(STATUSES), "description": "Only missions with this status."}
_LIMIT = {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT, "default": DEFAULT_LIMIT,
          "description": "Maximum number of items."}

TOOLS = [
    {
        "name": "courier_about",
        "title": "About Courier",
        "description": "What Courier is and what this read-only server can show.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": _READ_ONLY,
    },
    {
        "name": "courier_status",
        "title": "Automation status",
        "description": "One status card: RUNNING, IDLE, BLOCKED, ATTENTION or NOT_CONFIGURED, with a short reason.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": _READ_ONLY,
    },
    {
        "name": "list_missions",
        "title": "List missions",
        "description": "Missions from the receipt read model (POSTED, FINAL_DONE, BLOCKED, ERROR).",
        "inputSchema": {"type": "object", "properties": {"status": _STATUS_FILTER, "limit": _LIMIT},
                        "additionalProperties": False},
        "annotations": _READ_ONLY,
    },
    {
        "name": "get_mission",
        "title": "Get mission",
        "description": "One mission by its mission_id.",
        "inputSchema": {"type": "object",
                        "properties": {"mission_id": {"type": "string", "minLength": 1, "maxLength": 200}},
                        "required": ["mission_id"], "additionalProperties": False},
        "annotations": _READ_ONLY,
    },
    {
        "name": "list_receipts",
        "title": "List receipts",
        "description": "Receipts from the receipt read model, including a verified result when one was recorded.",
        "inputSchema": {"type": "object", "properties": {"limit": _LIMIT}, "additionalProperties": False},
        "annotations": _READ_ONLY,
    },
    {
        "name": "receipts_summary",
        "title": "Receipts summary",
        "description": "The receipt read model's counts per status, total, and latest update time.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": _READ_ONLY,
    },
]
TOOL_NAMES = frozenset(tool["name"] for tool in TOOLS)


class ToolError(Exception):
    """Invalid arguments. Reported to the client as a tool result with isError."""


class Source:
    """Either a configured state directory or bundled demo data, never both."""

    def __init__(self, state_dir=None, demo: bool = False):
        if demo == (state_dir is not None):
            raise ValueError("exactly one of state_dir or demo")
        self.state_dir = state_dir
        self.demo = demo

    def snapshot(self, now: datetime) -> Snapshot:
        if self.demo:
            return demo_snapshot(now)
        return read_state_dir(self.state_dir)


def call_tool(source: Source, name: str, arguments, now: datetime | None = None) -> dict:
    if name not in TOOL_NAMES:
        raise KeyError(name)
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise ToolError("arguments must be an object")
    allowed = set(next(t for t in TOOLS if t["name"] == name)["inputSchema"]["properties"])
    unknown = set(arguments) - allowed
    if unknown:
        raise ToolError("unknown argument(s): " + ", ".join(sorted(map(str, unknown))))
    moment = now or datetime.now(timezone.utc)
    if name == "courier_about":
        return dict(ABOUT, version=__version__, data="DEMO" if source.demo else "LIVE")
    snapshot = source.snapshot(moment)
    base = {"source": snapshot.source, "readable": snapshot.readable}
    if name == "courier_status":
        return dict(base, card=automation_card(snapshot, moment))
    if name == "list_missions":
        status = arguments.get("status")
        if status is not None and status not in STATUSES:
            raise ToolError("status must be one of " + ", ".join(STATUSES))
        limit = _limit(arguments)
        rows = _shown_missions(snapshot)
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        return dict(base, total=len(rows), missions=rows[:limit])
    if name == "get_mission":
        mission_id = arguments.get("mission_id")
        if not isinstance(mission_id, str) or not 0 < len(mission_id) <= 200:
            raise ToolError("mission_id must be a non-empty string")
        match = [row for row in _shown_missions(snapshot) if row["mission_id"] == mission_id]
        return dict(base, found=bool(match), mission=match[0] if match else None)
    if name == "list_receipts":
        limit = _limit(arguments)
        if snapshot.model_receipts is not None:
            rows = [dict(row) for row in snapshot.model_receipts]
        else:
            rows = [_receipt(row) for row in snapshot.missions if row["accepted_result_id"]]
        return dict(base, total=len(rows), receipts=rows[:limit])
    if snapshot.model_summary is not None:
        summary = snapshot.model_summary
        return dict(base, counts=dict(summary["counts"]), total=summary["total"],
                    last_updated=summary["last_updated"],
                    bridge=summary["bridge"], results=summary["results"])
    counts = {status: 0 for status in STATUSES}
    for row in snapshot.missions:
        counts[effective_status(row)] += 1
    stamps = [row["updated_at"] for row in snapshot.missions if row["updated_at"]]
    return dict(base, counts=counts, total=len(snapshot.missions),
                receipts=sum(1 for row in snapshot.missions if row["accepted_result_id"]),
                last_updated=max(stamps) if stamps else None)


def _shown_missions(snapshot: Snapshot) -> list[dict]:
    """Real mode returns the read model's receipts. Demo keeps the synthetic rows."""
    if snapshot.model_receipts is not None:
        return [dict(row) for row in snapshot.model_receipts]
    return [public_row(row) for row in snapshot.missions]


def _receipt(row: dict) -> dict:
    return {
        "mission_id": row["mission_id"],
        "task_id": row["task_id"],
        "goal_id": row["goal_id"],
        "status": effective_status(row),
        "accepted_result_id": row["accepted_result_id"],
        "evidence_ref": row["evidence_ref"],
        "updated_at": row["updated_at"],
    }


def _limit(arguments) -> int:
    value = arguments.get("limit", DEFAULT_LIMIT)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_LIMIT:
        raise ToolError(f"limit must be an integer from 1 to {MAX_LIMIT}")
    return value


def tool_result(payload: dict, is_error: bool = False) -> dict:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if len(text.encode("utf-8")) > MAX_RESULT_BYTES:
        payload = {"error": "RESULT_TOO_LARGE", "detail": "Ask for fewer items with a smaller limit."}
        text = json.dumps(payload, sort_keys=True)
        is_error = True
    result = {"content": [{"type": "text", "text": text}], "isError": is_error}
    if not is_error:
        result["structuredContent"] = payload
    return result
