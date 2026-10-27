"""RAID-OFFIZIER V1: one-shot Event → Decision. Not an orchestrator.

Pure function. No LLM, no network, no ledger writes, no scheduler, no second queue.
One call reads a status (plain dict or a local JSON file) and prints one Decision.
It never merges, force-pushes, bypasses STOP, or starts a paid agent.

Hard limits (also on every Decision under ``limits``):
SINGLE_WRITER=YES (Acc1), HEAVY_JOB_LIMIT=1, UNKNOWN_COST=BLOCK,
AUTONOMOUS_SPEND_LIMIT_EUR=0.

    python -m tools.automation.raid_officer --from-status FILE [--decisions-out FILE]

Exit codes: 0 decision on stdout · 2 usage · 3 status missing/unreadable ·
4 status is not a usable JSON object · 6 the optional local fixture could not be written.

``--decisions-out`` is the only side effect: it appends the same Decision line to a
local fixture file. The default invocation only writes stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

FORMAT = "courier-raid-officer-decision/1"
WRITER = "Acc1"
LIMITS = {
    "AUTONOMOUS_SPEND_LIMIT_EUR": 0,
    "HEAVY_JOB_LIMIT": 1,
    "SINGLE_WRITER": "YES",
    "SINGLE_WRITER_ACCOUNT": WRITER,
    "UNKNOWN_COST": "BLOCK",
}
EXIT_OK, EXIT_USAGE, EXIT_UNREADABLE, EXIT_BAD_STATUS, EXIT_WRITE = 0, 2, 3, 4, 6

BANNED_REQUESTS = {
    "merge", "force_push", "forcepush", "push_force",
    "ready_for_review", "mark_ready", "stop_bypass", "bypass_stop",
}
COST_BEARING = {"start_paid_agent", "paid_agent", "start_agent", "model_call", "heavy_job"}
WRITE_REQUESTS = {"write", "ledger_write", "release_writer", "patch"}
RELEASE_REQUESTS = {"", "write", "ledger_write", "release_writer"}
GREEN_WORDS = {"GREEN", "GRUEN", "GRUN"}
STOP_WORDS = {"STOP", "MUSE_STOP", "HALT"}
NO_PROGRESS_KINDS = {"NO_PROGRESS", "STALLED"}
NO_PROGRESS_JOURNAL = {"no_progress", "stalled"}
DIAGNOSED_ACTIONS = {"DIAGNOSE", "HOLD", "ESCALATE"}


class StatusError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _word(value) -> str:
    return _text(value).upper().replace("Ü", "U").replace("Ä", "A").replace("Ö", "O").replace("-", "_").replace(" ", "_")


def normalize_gate(value) -> str:
    """Map a gate word. Anything that is not explicitly GREEN or STOP is ROT (fail closed)."""
    word = _word(value)
    if word in STOP_WORDS:
        return "STOP"
    if word in GREEN_WORDS:
        return "GREEN"
    return "ROT"


def _known_gate_word(value) -> str | None:
    word = _word(value)
    if word in STOP_WORDS or word in GREEN_WORDS or word in {"ROT", "RED", "BLOCKED", "CLOSED", "FAIL", "FAILED", "YELLOW", "AMBER"}:
        return normalize_gate(value)
    return None


def _kind(event: dict) -> str:
    return _word(event.get("kind") or event.get("type") or event.get("event"))


def _blocker(*sources) -> str:
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key in ("blocker", "marker", "checkpoint"):
            text = _text(source.get(key))
            if text:
                return text
    return ""


def _object(value, label: str) -> dict:
    if value is None:
        return {}
    if isinstance(value, str):
        text = value.strip()
        return {"status": text} if text else {}
    if isinstance(value, dict):
        return dict(value)
    raise StatusError(EXIT_BAD_STATUS, f"{label} must be an object")


def _cost_kind(status: dict, requested: str) -> str:
    """absent | zero | positive | unknown. Non-finite, bool, negative, and blank costs are unknown."""
    has_cost = "cost_eur" in status or "cost_known" in status
    if not has_cost:
        return "unknown" if requested in COST_BEARING else "absent"
    if status.get("cost_known") is False:
        return "unknown"
    if "cost_eur" not in status:
        return "unknown"
    cost = status.get("cost_eur")
    if cost is None or (isinstance(cost, str) and cost.strip().lower() in {"", "unknown", "none", "null"}):
        return "unknown"
    if not (isinstance(cost, (int, float)) and not isinstance(cost, bool) and math.isfinite(cost)) or cost < 0:
        return "unknown"
    return "zero" if cost == 0 else "positive"


def _heavy_running(status: dict) -> int | None:
    if "heavy_jobs_running" not in status:
        return 0
    raw = status.get("heavy_jobs_running")
    if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
        return raw
    return None


def _priors(status: dict) -> list[dict]:
    items: list[dict] = []
    if "prior_decision" in status and status.get("prior_decision") is not None:
        single = status.get("prior_decision")
        if not isinstance(single, dict):
            raise StatusError(EXIT_BAD_STATUS, "prior_decision must be an object")
        items.append(single)
    many = status.get("prior_decisions", [])
    if many is None:
        many = []
    if not isinstance(many, list):
        raise StatusError(EXIT_BAD_STATUS, "prior_decisions must be a list")
    for item in many:
        if not isinstance(item, dict):
            raise StatusError(EXIT_BAD_STATUS, "prior_decisions entries must be objects")
        items.append(item)
    return items


def _event_from_status(status: dict) -> dict:
    if "event" in status and status.get("event") is not None:
        event = status.get("event")
        if not isinstance(event, dict):
            raise StatusError(EXIT_BAD_STATUS, "event must be an object")
        return dict(event)
    raw_line = status.get("event_line")
    if isinstance(raw_line, str) and raw_line.strip():
        try:
            parsed = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise StatusError(EXIT_BAD_STATUS, f"event_line is not JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise StatusError(EXIT_BAD_STATUS, "event_line must be a JSON object")
        return parsed
    return {}


def _skip(status: dict) -> tuple[bool, str, str]:
    skip = status.get("skip_marker")
    if skip is None or skip is False:
        return False, "", ""
    if skip is True:
        return True, "", ""
    if isinstance(skip, str):
        return (bool(skip.strip()), skip.strip(), "")
    if isinstance(skip, dict):
        present = bool(skip.get("present", True))
        marker = _text(skip.get("marker") or skip.get("checkpoint") or skip.get("id"))
        return present, marker, _text(skip.get("ref"))
    return True, "", ""


def _gate_of(status: dict, watchdog: dict) -> tuple[str, bool]:
    """Return (gate, conflict). A disagreement between the explicit gate and the watchdog fails closed to ROT."""
    explicit = status.get("gate")
    explicit_gate = normalize_gate(explicit) if isinstance(explicit, str) else None
    watched = None
    for key in ("gate", "status", "dps", "state"):
        watched = _known_gate_word(watchdog.get(key))
        if watched:
            break
    if explicit_gate is None:
        top = _known_gate_word(status.get("status"))
        if top:
            explicit_gate = top
    if explicit_gate and watched and explicit_gate != watched:
        return "ROT", True
    if explicit_gate:
        return explicit_gate, False
    if watched:
        return watched, False
    return "ROT", False


def _fingerprint(workkey: str, gate: str, stop: bool, kind: str, blocker: str) -> str:
    payload = {"blocker": blocker, "event_kind": kind, "gate": gate, "stop": bool(stop), "workkey": workkey}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _view(status: dict) -> dict:
    if not isinstance(status, dict):
        raise StatusError(EXIT_BAD_STATUS, "status must be a JSON object")
    watchdog = _object(status.get("watchdog"), "watchdog")
    journal = _object(status.get("journal"), "journal")
    raw_lease = status.get("lease")
    lease = {"valid": raw_lease} if isinstance(raw_lease, bool) else _object(raw_lease, "lease")
    event = _event_from_status(status)
    skip_present, skip_marker, skip_ref = _skip(status)
    if skip_present:
        event.setdefault("kind", "SKIP")
        if skip_marker and not _text(event.get("marker")):
            event["marker"] = skip_marker
        if skip_ref and not _text(event.get("ref")):
            event["ref"] = skip_ref
    kind = _kind(event)
    workkey = _text(status.get("workkey")) or _text(watchdog.get("workkey")) or _text(lease.get("workkey"))
    if not workkey:
        raise StatusError(EXIT_BAD_STATUS, "status.workkey is required")
    owner = _text(status.get("owner") or status.get("workkey_owner"))
    gate, conflict = _gate_of(status, watchdog)
    stop = gate == "STOP" or kind in {"STOP", "MUSE_STOP"}
    if "stop" in status and status.get("stop") is not False and status.get("stop") is not None:
        stop = True  # explicit STOP, or an unreadable flag: fail closed, never a bypass
    forced_invalid = kind == "LEASE_INVALID" or lease.get("stale") is True or lease.get("invalid") is True
    if "lease_valid" in status and "valid" not in lease:
        lease["valid"] = status.get("lease_valid")
    lease_valid = lease.get("valid") is True and not forced_invalid
    blocker = _blocker(event, journal)
    no_progress = False
    if status.get("progress") is False or kind in NO_PROGRESS_KINDS:
        no_progress = True
    elif "progress" not in status and _text(journal.get("status")).lower() in NO_PROGRESS_JOURNAL:
        no_progress = True
    requested = _word(status.get("requested_action")).lower()
    evidence: list[str] = []
    incoming = status.get("evidence_refs") or []
    if isinstance(incoming, str):
        incoming = [incoming]
    if not isinstance(incoming, list):
        raise StatusError(EXIT_BAD_STATUS, "evidence_refs must be a list")
    inputs = []
    if "watchdog" in status or watchdog:
        inputs.append("watchdog")
    if any(key in status for key in ("event", "event_line", "events_jsonl")) or event:
        inputs.append("event")
    if "skip_marker" in status or "skip_marker_file" in status:
        inputs.append("skip_marker")
    if "lease" in status or "lease_file" in status or "lease_valid" in status:
        inputs.append("lease")
    if "journal" in status or "journal_file" in status:
        inputs.append("journal")
    return {
        "actor": _text(status.get("actor")) or owner or WRITER,
        "blocker": blocker,
        "conflict": conflict,
        "cost": _cost_kind(status, requested),
        "diagnosis_done": status.get("diagnosis_done") is True,
        "escalated_flag": status.get("escalated") is True,
        "event": event,
        "evidence_in": incoming,
        "fingerprint": _fingerprint(workkey, gate, stop, kind, blocker),
        "gate": gate,
        "heavy_running": _heavy_running(status),
        "inputs": inputs,
        "journal": journal,
        "kind": kind,
        "lease": lease,
        "lease_valid": lease_valid,
        "no_progress": no_progress,
        "priors": _priors(status),
        "requested_action": requested,
        "skip_present": skip_present,
        "stop": stop,
        "watchdog": watchdog,
        "workkey": workkey,
        "workkey_owner": owner,
    }


def _same(view: dict) -> list[dict]:
    fingerprint = view["fingerprint"]
    return [item for item in view["priors"] if item.get("fingerprint") == fingerprint]


def _diagnosed(view: dict, same: list[dict]) -> bool:
    if view["diagnosis_done"]:
        return True
    return any(item.get("next_action") in DIAGNOSED_ACTIONS or item.get("case") in {"A", "B", "F", "STOP"} for item in same)


def _escalated(view: dict, same: list[dict]) -> bool:
    if view["escalated_flag"]:
        return True
    for item in same:
        if item.get("next_action") == "ESCALATE":
            return True
        count = item.get("escalation_count")
        if item.get("case") == "F" and isinstance(count, int) and not isinstance(count, bool) and count >= 1:
            return True
    return False


def _can_release(view: dict) -> bool:
    """RELEASE_WRITER only for Acc1, on a GREEN gate, with lease.valid exactly True, and no STOP."""
    if view["gate"] != "GREEN" or view["stop"] or not view["lease_valid"]:
        return False
    if view["actor"] != WRITER or view["workkey_owner"] != WRITER:
        return False
    lease = view["lease"]
    if _text(lease.get("owner")) != WRITER:
        return False
    bound = _text(lease.get("workkey"))
    if bound and bound != view["workkey"]:
        return False
    return True


def _refs(view: dict) -> list[str]:
    found: list[str] = []

    def add(value) -> None:
        if isinstance(value, (list, tuple)):
            for item in value:
                add(item)
            return
        text = _text(value) if not isinstance(value, (int, float)) else ""
        if isinstance(value, str):
            text = value.strip()
        if text and text not in found:
            found.append(text)

    add(view["evidence_in"])
    add(view["event"].get("ref"))
    if view["blocker"]:
        add(f"blocker:{view['blocker']}")
    marker = _text(view["event"].get("marker"))
    if marker:
        add(f"skip:{marker}")
    add(view["watchdog"].get("ref"))
    add(view["journal"].get("ref"))
    add(view["lease"].get("ref"))
    add(f"gate:{view['gate']}")
    if view["conflict"]:
        add("gate:conflict")
    if not found:
        add(f"workkey:{view['workkey']}")
    return found


def _detail(view: dict) -> str:
    for source in (view["event"], view["journal"]):
        text = _text(source.get("detail") or source.get("message"))
        if text:
            return text
    return ""


def _choose(view: dict, same: list[dict]) -> tuple[str, str, str, bool, int, str | None, bool, bool]:
    """Return action, case, reason, coalesced, escalation_count, escalate_to, write_allowed, ledger_write_allowed."""
    requested = view["requested_action"]
    blocker = view["blocker"]
    if requested in BANNED_REQUESTS:
        return ("BLOCK_BANNED", "BANNED",
                f"{requested} is refused; raid officer does not merge, force-push, mark ready, or bypass STOP",
                False, 0, None, False, False)
    if requested in COST_BEARING:
        return _choose_cost(view)
    if requested in WRITE_REQUESTS and view["actor"] != view["workkey_owner"]:
        rightful = view["workkey_owner"] or "unset"
        return ("DENY_NINJA", "D",
                f"anti-ninja: actor {view['actor']} is not the owner {rightful} of {view['workkey']}; write refused",
                False, 0, None, False, False)

    diagnosed = _diagnosed(view, same)
    escalated = _escalated(view, same)
    if view["gate"] == "GREEN" and not view["stop"]:
        return _choose_green(view, same, diagnosed)

    if view["no_progress"] and escalated:
        shown = blocker or "unspecified"
        return ("HOLD", "F",
                f"escalation already sent once for blocker {shown}; waiting for a state change",
                True, 1, None, False, False)
    if view["no_progress"] and diagnosed:
        detail = _detail(view)
        shown = blocker or "unspecified"
        if detail:
            reason = f"no progress; blocker {shown}: {detail}; single escalation to Ultra"
        else:
            reason = f"no progress; blocker {shown}; single escalation to Ultra"
        return ("ESCALATE", "F", reason, False, 1, "Ultra", False, False)
    if diagnosed:
        case = "STOP" if view["stop"] else "B"
        if view["stop"]:
            reason = "STOP remains; coalesced; no bypass and no repeat diagnose"
        elif view["conflict"]:
            reason = "gate still ROT (watchdog and gate disagree); coalesced; no repeat diagnose"
        else:
            reason = "gate still ROT for the same event; coalesced; no repeat diagnose and no paid agent"
        return ("HOLD", case, reason, True, 0, None, False, False)

    if view["stop"]:
        reason = "STOP blocks writes; no bypass; read-only diagnose"
    elif view["conflict"]:
        reason = "watchdog and gate disagree; fail closed to ROT; read-only diagnose"
    else:
        reason = "gate ROT blocks writes; read-only diagnose"
    if blocker:
        reason = f"{reason} ({blocker})"
    case = "STOP" if view["stop"] else "A"
    return ("DIAGNOSE", case, reason, False, 0, None, False, False)


def _choose_cost(view: dict) -> tuple:
    if view["cost"] == "unknown":
        return ("BLOCK_UNKNOWN_COST", "E",
                "UNKNOWN_COST=BLOCK; paid agent not started; AUTONOMOUS_SPEND_LIMIT_EUR=0",
                False, 0, None, False, False)
    running = view["heavy_running"]
    if running is None:
        return ("BLOCK_HEAVY", "HEAVY",
                "HEAVY_JOB_LIMIT=1; heavy job count unreadable; not started",
                False, 0, None, False, False)
    if running >= LIMITS["HEAVY_JOB_LIMIT"]:
        return ("BLOCK_HEAVY", "HEAVY",
                "HEAVY_JOB_LIMIT=1; a heavy job is already running; not started",
                False, 0, None, False, False)
    if view["requested_action"] == "heavy_job":
        return ("BLOCK_HEAVY", "HEAVY",
                "HEAVY_JOB_LIMIT=1; raid officer does not start heavy jobs",
                False, 0, None, False, False)
    if view["cost"] == "positive":
        return ("BLOCK_SPEND", "SPEND",
                "AUTONOMOUS_SPEND_LIMIT_EUR=0; paid agent not started",
                False, 0, None, False, False)
    return ("BLOCK_PAID_AGENT", "PAID",
            "paid agent not started; AUTONOMOUS_SPEND_LIMIT_EUR=0",
            False, 0, None, False, False)


def _choose_green(view: dict, same: list[dict], diagnosed: bool) -> tuple:
    requested = view["requested_action"]
    if requested not in RELEASE_REQUESTS:
        if diagnosed:
            return ("HOLD", "C", "gate GREEN; read-only request already decided; coalesced",
                    True, 0, None, False, False)
        return ("DIAGNOSE", "C", "gate GREEN; requested action is read-only; writer not released",
                False, 0, None, False, False)
    if view["workkey_owner"] == view["actor"] and view["actor"] not in ("", WRITER):
        return ("BLOCK_SINGLE_WRITER", "WRITER",
                "SINGLE_WRITER=YES; only Acc1 may be released to write the ledger",
                any(item.get("next_action") == "BLOCK_SINGLE_WRITER" for item in same),
                0, None, False, False)
    if _can_release(view):
        return ("RELEASE_WRITER", "C",
                "gate GREEN and lease.valid for Acc1; RELEASE_WRITER",
                False, 0, None, True, True)
    if not view["lease_valid"]:
        reason = "gate GREEN but lease.valid is not true; RELEASE_WRITER refused"
    elif _text(view["lease"].get("workkey")) not in ("", view["workkey"]):
        reason = "gate GREEN but lease workkey does not match; RELEASE_WRITER refused"
    else:
        reason = "gate GREEN but lease is not held by Acc1; RELEASE_WRITER refused"
    coalesced = any(item.get("next_action") == "WAIT_LEASE" for item in same)
    return ("WAIT_LEASE", "C", reason, coalesced, 0, None, False, False)


def _enforce(view: dict, action: str, case: str, reason: str, write_allowed: bool, ledger_write_allowed: bool):
    """Last word on the hard bans, so a branch cannot release a writer or spend."""
    if action == "RELEASE_WRITER" and not _can_release(view):
        action, case = "WAIT_LEASE", "C"
        reason = "RELEASE_WRITER refused without a valid Acc1 lease on a GREEN gate"
        write_allowed = ledger_write_allowed = False
    if view["stop"] and action == "RELEASE_WRITER":
        action, case = "DIAGNOSE", "STOP"
        reason = "STOP blocks writer release; no bypass"
        write_allowed = ledger_write_allowed = False
    if action in {"MERGE", "FORCE_PUSH", "STOP_BYPASS", "READY_FOR_REVIEW"}:
        action, case = "BLOCK_BANNED", "BANNED"
        write_allowed = ledger_write_allowed = False
    if action != "RELEASE_WRITER":
        write_allowed = ledger_write_allowed = False
    return action, case, reason, write_allowed, ledger_write_allowed


def decide(status: dict) -> dict:
    """Map one status dict to one Decision. Does not read or write the ledger and does not touch the network."""
    view = _view(status)
    same = _same(view)
    action, case, reason, coalesced, escalation_count, escalate_to, write_allowed, ledger_write_allowed = _choose(view, same)
    action, case, reason, write_allowed, ledger_write_allowed = _enforce(
        view, action, case, reason, write_allowed, ledger_write_allowed)
    owner = view["workkey_owner"] or WRITER
    if action == "ESCALATE":
        owner = "Ultra"
    elif action == "DENY_NINJA":
        owner = view["workkey_owner"] or "unset"
    elif action == "RELEASE_WRITER":
        owner = WRITER
    return {
        "actor": view["actor"],
        "blocker": view["blocker"] or None,
        "case": case,
        "coalesced": coalesced,
        "escalate_to": escalate_to,
        "escalation_count": escalation_count,
        "evidence_refs": _refs(view),
        "exit_code": EXIT_OK,
        "fingerprint": view["fingerprint"],
        "format": FORMAT,
        "gate": view["gate"],
        "heavy_job_started": False,
        "idempotency_key": f"{view['workkey']}@{view['fingerprint'][:16]}",
        "inputs": list(view["inputs"]),
        "lease_valid": view["lease_valid"],
        "ledger_write_allowed": ledger_write_allowed,
        "limits": dict(LIMITS),
        "model_call": False,
        "next_action": action,
        "owner": owner,
        "reason": reason,
        "repeat": False,
        "requested_action": view["requested_action"],
        "spawn_agent": False,
        "spend_eur": 0,
        "start_paid_agent": False,
        "stop_bypass": False,
        "workkey": view["workkey"],
        "workkey_owner": view["workkey_owner"],
        "write_allowed": write_allowed,
    }


def _read_object(path: Path, label: str) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise StatusError(EXIT_UNREADABLE, f"{path}: {label} not found") from exc
    except OSError as exc:
        raise StatusError(EXIT_UNREADABLE, f"{path}: cannot read {label}: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StatusError(EXIT_BAD_STATUS, f"{path}: {label} is not valid JSON") from exc
    if not isinstance(data, dict):
        raise StatusError(EXIT_BAD_STATUS, f"{path}: {label} must be a JSON object")
    return data


def _sibling(base: Path, raw, label: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise StatusError(EXIT_BAD_STATUS, f"{label} must be a path")
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate


def _jsonl_event(path: Path, index: int) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise StatusError(EXIT_UNREADABLE, f"{path}: events.jsonl not found") from exc
    except OSError as exc:
        raise StatusError(EXIT_UNREADABLE, f"{path}: cannot read events.jsonl: {exc}") from exc
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise StatusError(EXIT_BAD_STATUS, f"{path}: events.jsonl has no events")
    try:
        raw = lines[index]
    except IndexError as exc:
        raise StatusError(EXIT_BAD_STATUS, f"{path}: event_index {index} out of range") from exc
    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StatusError(EXIT_BAD_STATUS, f"{path}: event line is not JSON") from exc
    if not isinstance(event, dict):
        raise StatusError(EXIT_BAD_STATUS, f"{path}: event line must be an object")
    return event


def _read_priors(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise StatusError(EXIT_UNREADABLE, f"{path}: prior decisions not found") from exc
    except OSError as exc:
        raise StatusError(EXIT_UNREADABLE, f"{path}: cannot read prior decisions: {exc}") from exc
    stripped = text.strip()
    if not stripped:
        return []
    try:
        if stripped.startswith("["):
            data = json.loads(stripped)
            if not isinstance(data, list):
                raise StatusError(EXIT_BAD_STATUS, f"{path}: prior decisions must be a list")
            rows = data
        else:
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise StatusError(EXIT_BAD_STATUS, f"{path}: prior decisions are not valid JSON") from exc
    if not all(isinstance(row, dict) for row in rows):
        raise StatusError(EXIT_BAD_STATUS, f"{path}: prior decisions entries must be objects")
    return rows


def load_status(path: str | os.PathLike) -> dict:
    """Read a status JSON file and inline any local watchdog, event, skip, lease, or journal files it names.

    Inline keys win over files. This function only reads. It does not write.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise StatusError(EXIT_UNREADABLE, f"{path}: status file not found") from exc
    except OSError as exc:
        raise StatusError(EXIT_UNREADABLE, f"{path}: cannot read status: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StatusError(EXIT_BAD_STATUS, f"{path}: status is not valid JSON") from exc
    if not isinstance(data, dict):
        raise StatusError(EXIT_BAD_STATUS, f"{path}: status must be a JSON object")
    return _resolve_files(data, path.parent)


def _resolve_files(data: dict, base: Path) -> dict:
    resolved = dict(data)
    if "watchdog_file" in data and "watchdog" not in data:
        watchdog_path = _sibling(base, data.get("watchdog_file"), "watchdog_file")
        watchdog = _read_object(watchdog_path, "watchdog")
        if "ref" not in watchdog:
            watchdog["ref"] = watchdog_path.name
        resolved["watchdog"] = watchdog
        if "gate" not in resolved:
            for key in ("gate", "status", "dps", "state"):
                if _known_gate_word(watchdog.get(key)):
                    resolved["gate"] = watchdog[key]
                    break
        if "workkey" not in resolved and _text(watchdog.get("workkey")):
            resolved["workkey"] = watchdog["workkey"]
    if "events_jsonl" in data and "event" not in data and "event_line" not in data:
        index = data.get("event_index", -1)
        if isinstance(index, bool) or not isinstance(index, int):
            raise StatusError(EXIT_BAD_STATUS, "event_index must be an integer")
        resolved["event"] = _jsonl_event(_sibling(base, data.get("events_jsonl"), "events_jsonl"), index)
    if "skip_marker_file" in data and "skip_marker" not in data:
        marker_path = _sibling(base, data.get("skip_marker_file"), "skip_marker_file")
        if marker_path.is_file():
            try:
                body = marker_path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise StatusError(EXIT_UNREADABLE, f"{marker_path}: cannot read skip marker: {exc}") from exc
            resolved["skip_marker"] = {"present": True, "marker": body or marker_path.name, "ref": marker_path.name}
        else:
            resolved["skip_marker"] = {"present": False, "ref": marker_path.name}
    if "lease_file" in data and "lease" not in data:
        resolved["lease"] = _read_object(_sibling(base, data.get("lease_file"), "lease_file"), "lease")
    if "journal_file" in data and "journal" not in data:
        resolved["journal"] = _read_object(_sibling(base, data.get("journal_file"), "journal_file"), "journal")
    if "prior_decisions_file" in data and "prior_decisions" not in data and "prior_decision" not in data:
        resolved["prior_decisions"] = _read_priors(_sibling(base, data.get("prior_decisions_file"), "prior_decisions_file"))
    return resolved


def _append_decision(path: Path, decision: dict) -> None:
    path.parent.mkdir(parents=False, exist_ok=True)
    line = json.dumps(decision, sort_keys=True).encode("utf-8") + b"\n"
    with open(path, "ab") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tools.automation.raid_officer",
        description="One-shot RAID-OFFIZIER decision. Event status in, Decision JSON out. No ledger writes.",
    )
    parser.add_argument("--from-status", required=True, help="local JSON status (watchdog, event, skip, lease, journal)")
    parser.add_argument("--decisions-out", help="append the Decision JSON line to this local fixture file")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return EXIT_OK if exc.code == 0 else EXIT_USAGE
    if not args.from_status:
        print("RAID_OFFICER_ERROR code=2 --from-status is required", file=sys.stderr)
        return EXIT_USAGE
    try:
        decision = decide(load_status(args.from_status))
    except StatusError as exc:
        print(f"RAID_OFFICER_ERROR code={exc.code} {exc}", file=sys.stderr)
        return exc.code
    if args.decisions_out:
        try:
            _append_decision(Path(args.decisions_out), decision)
        except OSError as exc:
            print(f"RAID_OFFICER_ERROR code={EXIT_WRITE} cannot write decision fixture: {exc}", file=sys.stderr)
            return EXIT_WRITE
    print(json.dumps(decision, sort_keys=True))
    return decision["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
