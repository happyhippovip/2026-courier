#!/usr/bin/env python3
"""Pilot file check plus a fail-closed PRE_CODEX_READY decision.

File presence is reported as a boolean. It is not a test run, and a JSON
narrative is not one either. This module never emits PRE_CODEX_READY=YES.
"""
import json
import sys
from pathlib import Path

METRIC_TARGETS = (
    ("SETUP_TIME_MAX_MINUTES", 15),
    ("HIPG_HUMAN_INTERVENTIONS_PER_GOAL", 0),
    ("RSR_RESTART_SURVIVAL_RATE", "100%"),
    ("NDR_NO_DUPLICATE_REPLAY", "100%"),
    ("SUPPORT_EFFORT_MINUTES", 5),
    ("PROVIDER_COST_CLASS", "SUBSCRIPTION_OR_FREE"),
    ("TIME_TO_USEFUL_RESULT_MINUTES", 10),
)
CLAIM_BLOCKER = "report shape is not a durable PRE_CODEX_READY claim"
FILE_PREREQUISITES = ("PRE_CODEX_HANDOFF", "PROOF_CARD", "PILOT_DUMMY_TASK")


def _sha_ok(value) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(ch in "0123456789abcdef" for ch in value)


def evaluate_pre_codex_ready(report_path, *, expected_sha):
    """Read a pytest-shaped report file. Never authorize the product claim."""
    reasons = []
    sha = expected_sha if _sha_ok(expected_sha) else None
    if sha is None:
        reasons.append("final_sha missing")
    path = Path(report_path) if report_path else None
    payload = None
    if path is None or not path.is_file():
        reasons.append("pytest report missing")
    else:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            reasons.append("pytest report unreadable")
        if payload is not None and not isinstance(payload, dict):
            reasons.append("pytest report malformed")
            payload = None
        if isinstance(payload, dict):
            if payload.get("source") != "PYTEST":
                reasons.append("source is not a pytest report")
            if sha is not None and payload.get("final_sha") != sha:
                reasons.append("report sha does not match final_sha")
            summary = payload.get("summary")
            if not isinstance(summary, dict):
                reasons.append("summary missing")
            else:
                if summary.get("failed") != 0:
                    reasons.append("failed tests")
                if summary.get("skipped") != 0:
                    reasons.append("skipped tests")
                passed = summary.get("passed")
                if not isinstance(passed, int) or passed < 1:
                    reasons.append("no passed tests")
    return {
        "gate": "PRE_CODEX_READY",
        "status": "NOT_READY",
        "claim_allowed": False,
        "receipt_shape": "OK" if not reasons else "REJECTED",
        "final_sha": sha,
        "blockers": [CLAIM_BLOCKER, *reasons],
    }


def load_pre_codex_receipts(path):
    """Reload append-only receipts. A stored YES is not honored."""
    file_path = Path(path)
    if not file_path.is_file():
        return []
    rows = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        decision = row.get("decision")
        if isinstance(decision, dict):
            decision = dict(decision)
            decision["claim_allowed"] = False
            decision["status"] = "NOT_READY"
            row = dict(row)
            row["decision"] = decision
        rows.append(row)
    return rows


def append_pre_codex_receipt(path, receipt) -> bool:
    """Append one receipt. The same event_id does not replay."""
    if not isinstance(receipt, dict):
        return False
    event_id = receipt.get("event_id")
    decision = receipt.get("decision")
    if not isinstance(event_id, str) or not event_id or not isinstance(decision, dict):
        return False
    file_path = Path(path)
    if any(row.get("event_id") == event_id for row in load_pre_codex_receipts(file_path)):
        return False
    stored_decision = dict(decision)
    stored_decision["claim_allowed"] = False
    stored_decision["status"] = "NOT_READY"
    line = json.dumps(
        {"event_id": event_id, "decision": stored_decision},
        sort_keys=True,
        separators=(",", ":"),
    )
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return True


def check_pilot_gate_readiness(evidence=None):
    evidence = evidence or {}
    repo_root = Path(__file__).resolve().parent.parent
    report = {
        "gate": "PILOT_READINESS_GATE",
        "status": "BLOCKED",
        "metrics": {
            name: {"target": target, "actual": None, "status": "NOT_PROVEN"}
            for name, target in METRIC_TARGETS
        },
        "prerequisites": {
            "PRE_CODEX_HANDOFF": (repo_root / "ops/ai/PRE_CODEX_HANDOFF.md").is_file(),
            "PROOF_CARD": (repo_root / "ops/ai/PROOF_CARD.md").is_file(),
            "PILOT_DUMMY_TASK": (repo_root / "ops/ai/PILOT_DUMMY_TASK.json").is_file(),
            "TARGETED_TESTS_GREEN": False,
        },
    }
    report["pre_codex"] = evaluate_pre_codex_ready(
        evidence.get("pytest_report"),
        expected_sha=evidence.get("final_sha"),
    )
    files_ok = all(report["prerequisites"][name] for name in FILE_PREREQUISITES)
    report["reason"] = "Missing prerequisites" if not files_ok else "PRE_CODEX_NOT_READY"
    print(json.dumps(report, indent=2))
    return 1

if __name__ == "__main__":
    sys.exit(check_pilot_gate_readiness())
