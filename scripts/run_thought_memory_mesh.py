#!/usr/bin/env python3
"""Channel-neutral, deterministic thought coverage and proposal preparation.

This program is deliberately local. It consumes explicitly supplied message
exports, keeps compact message id/hash checkpoints, reads Project Memory
read-only, and emits a *proposal* for the existing 086 Chief-approval gate.
It has no connector, OAuth, Slack, ChatGPT, Google, or memory-write behavior.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from build_memory_update_proposal import get_memory_commit, validate_proposal_against_schema

INITIAL_ANCHOR = "2026-08-25"
SUPPORTED_SOURCES = {
    "CHAT_EXPORT", "COURIER_EVENT", "WORK_RESULT", "GOOGLE_ANTIGRAVITY_RESULT", "SLACK"
}
PROTECTED_STATUS_LABELS = {
    "UNKNOWN", "CONFLICT", "EXTERNAL_STATUS", "POSSIBLY_OUTDATED", "HISTORICAL_DECISION", "USER_INTENT", "IDEA"
}
PROPOSAL_STATUS_MAP = {"USER_INTENT": "IDEA", "POSSIBLY_OUTDATED": "UNKNOWN"}
SENSITIVE_VALUE_PATTERN = re.compile(r"(?i)(ghp_[a-z0-9]{20,}|github_pat_[a-z0-9_]{20,}|sk-[a-z0-9]{20,}|AIza[0-9a-z_-]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")
SENSITIVE_FIELD_PATTERN = re.compile(r"(?i)(password|passphrase|secret|token|api[_-]?key|oauth|credential|cookie|session)")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def parse_timestamp(value: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include an explicit timezone")
    return parsed


def contains_sensitive_value(value: Any) -> bool:
    """Reject potential credentials before any payload reaches ledger or proposal."""
    if isinstance(value, str):
        return bool(SENSITIVE_VALUE_PATTERN.search(value))
    if isinstance(value, list):
        return any(contains_sensitive_value(item) for item in value)
    if isinstance(value, dict):
        for key, nested in value.items():
            if SENSITIVE_FIELD_PATTERN.search(str(key)) and nested not in (None, "", False):
                return True
            if contains_sensitive_value(nested):
                return True
    return False


def read_messages(path: Path) -> list[dict[str, Any]]:
    data = load_json(path, [])
    if not isinstance(data, list):
        raise ValueError("message input must be a JSON array")
    return data


def validate_messages(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    anchor = dt.date.fromisoformat(INITIAL_ANCHOR)
    for item in messages:
        if not isinstance(item, dict):
            rejected.append({"message_id": None, "reason": "message must be an object"})
            continue
        try:
            message_id, timestamp, source, payload = item["message_id"], item["timestamp"], item["source"], item["payload"]
            if not isinstance(message_id, str) or not message_id or source not in SUPPORTED_SOURCES or not isinstance(payload, dict):
                raise ValueError("invalid identity/source/payload")
            stamp = parse_timestamp(timestamp)
            if stamp.date() < anchor:
                raise ValueError("before historical anchor")
            expected_hash = canonical_hash(payload)
            if item.get("payload_hash") != expected_hash:
                raise ValueError("payload_hash mismatch")
            if item.get("schema_version") != "thought-message-1.0":
                raise ValueError("unsupported schema_version")
            if contains_sensitive_value(payload):
                raise ValueError("sensitive payload rejected")
        except (KeyError, TypeError, ValueError) as exc:
            rejected.append({"message_id": item.get("message_id"), "reason": str(exc)})
            continue
        prior = seen.get(message_id)
        if prior is not None:
            duplicates.append({"message_id": message_id, "payload_hash": expected_hash, "kind": "DUPLICATE" if prior == expected_hash else "ID_HASH_CONFLICT"})
            continue
        seen[message_id] = expected_hash
        valid.append({**item, "_datetime": stamp})
    valid.sort(key=lambda message: (message["_datetime"], message["message_id"]))
    return valid, rejected, duplicates


def describe_message(message: dict[str, Any] | None) -> dict[str, str] | None:
    if message is None:
        return None
    return {"message_id": message["message_id"], "timestamp": message["timestamp"], "payload_hash": message["payload_hash"]}


def scanner_ranges(messages: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], set[str]]:
    if not messages:
        return ({name: {"direction": direction, "message_count": 0, "message_id_digest": canonical_hash([]), "from": None, "to": None} for name, direction in {
            "THOUGHT_FORWARD_SCANNER": "FORWARD", "THOUGHT_REVERSE_SCANNER": "REVERSE", "THOUGHT_MIDPOINT_BACK_SCANNER": "REVERSE", "THOUGHT_MIDPOINT_FORWARD_SCANNER": "FORWARD"}.items()}, set())
    first, last = messages[0], messages[-1]
    midpoint = first["_datetime"] + (last["_datetime"] - first["_datetime"]) / 2
    forward = messages
    reverse = list(reversed(messages))
    midpoint_back = [message for message in reversed(messages) if message["_datetime"] <= midpoint]
    midpoint_forward = [message for message in messages if message["_datetime"] >= midpoint]
    specs = {
        "THOUGHT_FORWARD_SCANNER": ("FORWARD", forward),
        "THOUGHT_REVERSE_SCANNER": ("REVERSE", reverse),
        "THOUGHT_MIDPOINT_BACK_SCANNER": ("REVERSE", midpoint_back),
        "THOUGHT_MIDPOINT_FORWARD_SCANNER": ("FORWARD", midpoint_forward),
    }
    output = {}
    covered: set[str] = set()
    for name, (direction, scan) in specs.items():
        ids = [message["message_id"] for message in scan]
        covered.update(ids)
        output[name] = {"direction": direction, "from": scan[0]["timestamp"] if scan else None, "to": scan[-1]["timestamp"] if scan else None, "message_count": len(ids), "message_id_digest": canonical_hash(ids)}
    return output, covered


def find_calendar_gaps(messages: list[dict[str, Any]]) -> list[str]:
    if not messages:
        return []
    available_days = {message["_datetime"].date() for message in messages}
    day, end = dt.date.fromisoformat(INITIAL_ANCHOR), messages[-1]["_datetime"].date()
    gaps = []
    while day <= end:
        if day not in available_days:
            gaps.append(day.isoformat())
        day += dt.timedelta(days=1)
    return gaps


def status_for(message: dict[str, Any]) -> str:
    return str(message["payload"].get("status_label", "UNKNOWN"))


def scene_audit(messages: list[dict[str, Any]], rejected: list[dict[str, Any]], duplicates: list[dict[str, Any]], ranges: dict[str, dict[str, Any]], covered: set[str], prior_identity_conflicts: list[dict[str, Any]]) -> dict[str, Any]:
    all_ids = {message["message_id"] for message in messages}
    # Each non-empty scanner covers a chronological range; full ID lists are deliberately not duplicated in the ledger.
    overlaps = sorted(all_ids) if len([data for data in ranges.values() if data["message_count"]]) > 1 else []
    illegal_promotions = []
    for message in messages:
        payload = message["payload"]
        if payload.get("requested_status") == "VERIFIED_CURRENT" and status_for(message) in PROTECTED_STATUS_LABELS:
            illegal_promotions.append(message["message_id"])
    return {
        "coverage_complete": all_ids == covered,
        "uncovered_message_ids": sorted(all_ids - covered),
        "gaps": find_calendar_gaps(messages),
        "duplicate_findings": duplicates,
        "prior_identity_hash_conflicts": prior_identity_conflicts,
        "rejected_messages": rejected,
        "overlap_message_ids": overlaps,
        "illegal_status_promotions_blocked": illegal_promotions,
        "timestamp_order_checked": True,
    }


def thought_manager(delta: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only compact classified candidates; never promote input status."""
    candidates = []
    for message in delta:
        payload = message["payload"]
        summary = str(payload.get("summary", "")).strip()
        if not summary:
            continue
        candidates.append({
            "message_id": message["message_id"], "source": message["source"], "kind": str(payload.get("kind", "OPEN_QUESTION")),
            "summary": summary, "status_label": status_for(message), "payload_hash": message["payload_hash"],
            "requested_status": payload.get("requested_status"),
        })
    return candidates


def thought_boss_a(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[str]] = {key: [] for key in ("INTENT", "DECISION", "IDEA", "TASK", "OPEN_QUESTION", "OTHER")}
    for candidate in candidates:
        buckets[candidate["kind"] if candidate["kind"] in buckets else "OTHER"].append(candidate["message_id"])
    return {"independent_review": "THOUGHT_BOSS_A", "candidates_reviewed": len(candidates), "classification": buckets}


def thought_boss_b(candidates: list[dict[str, Any]], memory_commit: str) -> dict[str, Any]:
    findings = []
    accepted = []
    for candidate in candidates:
        status = candidate["status_label"]
        if candidate.get("requested_status") == "VERIFIED_CURRENT" and status in PROTECTED_STATUS_LABELS:
            findings.append({"message_id": candidate["message_id"], "decision": "BLOCKED", "reason": "protected status cannot be promoted by a message candidate"})
        elif status == "VERIFIED_CURRENT":
            findings.append({"message_id": candidate["message_id"], "decision": "BLOCKED", "reason": "new message alone cannot establish VERIFIED_CURRENT"})
        else:
            accepted.append(candidate)
    return {"independent_review": "THOUGHT_BOSS_B", "memory_commit_checked": memory_commit, "candidates_reviewed": len(candidates), "accepted_candidates": accepted, "findings": findings}


def build_proposal(accepted: list[dict[str, Any]], memory_commit: str) -> dict[str, Any] | None:
    if not accepted:
        return None
    changes = []
    for candidate in accepted:
        proposed_status = PROPOSAL_STATUS_MAP.get(candidate["status_label"], candidate["status_label"])
        if proposed_status not in {"VERIFIED_CURRENT", "EXTERNAL_STATUS", "HISTORICAL_DECISION", "PLANNED", "IDEA", "CONFLICT", "UNKNOWN", "STATUS_BOUNDARY", "PAUSED", "PAUSED_EXTERNAL_GATE", "DEFERRED", "NOT VERIFIED", "IN PROGRESS"}:
            proposed_status = "UNKNOWN"
        changes.append({
            "file": "OPEN_QUESTIONS.md",
            "action": "APPEND",
            "section": "Thought Memory Mesh proposals",
            "proposed_text": f"- **{proposed_status}** | Source message `{candidate['message_id']}` ({candidate['source']}); original classification `{candidate['status_label']}` retained in courier evidence. {candidate['summary']}",
            "status_label": proposed_status,
        })
    task_id = "THOUGHT-MEMORY-MESH"
    corr = "thought-mesh-" + canonical_hash([candidate["message_id"] for candidate in accepted])[:12]
    proposal = {
        "schema_version": "2.0",
        "proposal_id": f"prop-mem-{task_id}-{uuid.uuid4().hex[:8]}",
        "source_result_message_id": "thought-mesh-" + canonical_hash([candidate["payload_hash"] for candidate in accepted])[:16],
        "task_id": task_id,
        "correlation_id": corr,
        "memory_base_commit": memory_commit,
        "target_files": ["OPEN_QUESTIONS.md"],
        "proposed_changes": changes,
        "reason": "Channel-neutral Thought Coverage Mesh candidate(s), pending explicit Chief approval.",
        "status_labels": sorted({change["status_label"] for change in changes}),
        "source_references": [candidate["message_id"] for candidate in accepted],
        "requires_chief_approval": True,
        "created_at": utc_now(),
    }
    valid, reason = validate_proposal_against_schema(proposal)
    if not valid:
        raise ValueError(f"proposal validation failed: {reason}")
    return proposal


def build_delivery(proposal: dict[str, Any] | None) -> dict[str, Any] | None:
    if proposal is None:
        return None
    return {
        "schema_version": "chief-delivery-1.0",
        "delivery_id": "delivery-" + proposal["proposal_id"],
        "proposal_id": proposal["proposal_id"],
        "correlation_id": proposal["correlation_id"],
        "destination": "CHIEF_UNVERIFIED_CHANNEL",
        "delivery_status": "PREPARED_NOT_DELIVERED",
        "created_at": utc_now(),
    }


def run_mesh(messages: list[dict[str, Any]], prior_ledger: dict[str, Any], memory_repo: Path) -> dict[str, Any]:
    valid, rejected, duplicates = validate_messages(messages)
    prior = prior_ledger.get("processed_messages", {})
    prior_identity_conflicts = [
        {"message_id": message["message_id"], "previous_hash": prior[message["message_id"]], "incoming_hash": message["payload_hash"]}
        for message in valid if message["message_id"] in prior and prior[message["message_id"]] != message["payload_hash"]
    ]
    conflict_ids = {item["message_id"] for item in prior_identity_conflicts}
    delta = [message for message in valid if message["message_id"] not in prior and message["message_id"] not in conflict_ids]
    ranges, covered = scanner_ranges(valid)
    audit = scene_audit(valid, rejected, duplicates, ranges, covered, prior_identity_conflicts)
    processed = dict(prior)
    processed.update({message["message_id"]: message["payload_hash"] for message in valid if message["message_id"] not in conflict_ids})
    memory_commit = get_memory_commit(memory_repo)
    manager = thought_manager(delta)
    boss_a = thought_boss_a(manager)
    boss_b = thought_boss_b(manager, memory_commit)
    proposal = build_proposal(boss_b["accepted_candidates"], memory_commit)
    ledger = {
        "schema_version": "thought-coverage-ledger-1.0",
        "initial_anchor": INITIAL_ANCHOR,
        "earliest_available_message": describe_message(valid[0] if valid else None),
        "latest_available_message": describe_message(valid[-1] if valid else None),
        "scanner_ranges": ranges,
        "completed_checkpoints": {"last_confirmed_check": valid[-1]["timestamp"] if valid else None, "last_delta_count": len(delta)},
        "gaps": audit["gaps"],
        "overlaps": audit["overlap_message_ids"],
        "message_counts": {"input": len(messages), "valid_unique": len(valid), "delta_processed": len(delta), "duplicates": len(duplicates), "rejected": len(rejected)},
        "processed_messages": processed,
    }
    return {"coverage_ledger": ledger, "scene_audit": audit, "thought_manager": manager, "thought_boss_a": boss_a, "thought_boss_b": boss_b, "memory_update_proposal": proposal, "chief_delivery_adapter": build_delivery(proposal)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local channel-neutral Thought Memory Mesh")
    parser.add_argument("--messages", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--memory-repo", type=Path, default=Path("/Users/user/Downloads/2026-project-memory"))
    args = parser.parse_args()
    result = run_mesh(read_messages(args.messages), load_json(args.ledger, {}), args.memory_repo)
    args.ledger.parent.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.ledger.write_text(json.dumps(result["coverage_ledger"], indent=2) + "\n", encoding="utf-8")
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"proposal_created": result["memory_update_proposal"] is not None, "delta_processed": result["coverage_ledger"]["message_counts"]["delta_processed"]}))


if __name__ == "__main__":
    main()
