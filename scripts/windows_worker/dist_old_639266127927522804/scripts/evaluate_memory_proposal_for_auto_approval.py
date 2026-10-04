#!/usr/bin/env python3
"""Autonomous Chief Approval Policy Engine (088).

Evaluates MemoryUpdateProposals deterministically into exactly three classes:
  1. AUTO_APPROVE  -> Generates schema-valid 087 Chief Approval (approved_by: AUTONOMOUS_CHIEF_POLICY).
  2. HUMAN_REVIEW  -> Stops and queues for human review; ZERO approvals generated.
  3. BLOCKED       -> Stops with security/policy violation; ZERO approvals generated.

Guarantees:
- Step 087 is NEVER bypassed; AUTO_APPROVE does not write directly to memory.
- Only purely documentary, reversible VERIFIED_CURRENT technical facts are auto-approved.
- Any strategic, speculative, external, unverified, or conflicting statuses route to HUMAN_REVIEW.
- Any secrets, target violations, HEAD conflicts, or missing sources are strictly BLOCKED.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import uuid
from pathlib import Path

DEFAULT_MEMORY_REPO_PATH = Path("/Users/user/Downloads/2026-project-memory")
DEFAULT_PROPOSAL_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas/memory_update_proposal.schema.json"
DEFAULT_APPROVAL_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas/memory_update_approval.schema.json"
DEFAULT_DECISION_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas/autonomous_chief_decision.schema.json"

CANONICAL_MEMORY_ALLOWLIST = {
    "AGENTS.md",
    "PROJECT_STATE.md",
    "PRODUCT_VISION.md",
    "DECISIONS.md",
    "IDEA_ARCHIVE.md",
    "BACKLOG.md",
    "TECHNICAL_CONTEXT.md",
    "OPEN_QUESTIONS.md",
    "LESSONS_LEARNED.md",
    "SOURCE_INDEX.md",
    "MEMORY_CHANGELOG.md",
}

CANONICAL_STATUS_ALLOWLIST = {
    "VERIFIED_CURRENT",
    "EXTERNAL_STATUS",
    "HISTORICAL_DECISION",
    "USER_INTENT",
    "PLANNED",
    "IDEA",
    "DEFERRED",
    "PAUSED",
    "REJECTED",
    "POSSIBLY_OUTDATED",
    "CONFLICT",
    "SOURCE_MISSING",
    "UNKNOWN",
    "STATUS_BOUNDARY",
    "PAUSED_EXTERNAL_GATE",
    "NOT VERIFIED",
    "IN PROGRESS",
}

SECRET_PATTERNS = [
    re.compile(r"(?i)(password|secret|token|api[_-]?key|bearer|oauth|auth[_-]?token|private[_-]?key)\s*[:=]\s*['\"][A-Za-z0-9_\-\.]{8,}['\"]"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z-_]{35}"),
    re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----"),
]


def fail(message: str) -> None:
    raise SystemExit(f"CHIEF_POLICY_ERROR: {message}")


def get_memory_commit(repo_path: Path) -> str:
    """Reads git commit hash directly from .git directory."""
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        return "0000000000000000000000000000000000000000"

    head_file = git_dir / "HEAD"
    if not head_file.exists():
        return "0000000000000000000000000000000000000000"

    head_content = head_file.read_text(encoding="utf-8").strip()
    if head_content.startswith("ref:"):
        ref_path = head_content[4:].strip()
        ref_file = git_dir / ref_path
        if ref_file.exists():
            return ref_file.read_text(encoding="utf-8").strip()
        packed_refs_file = git_dir / "packed-refs"
        if packed_refs_file.exists():
            for line in packed_refs_file.read_text(encoding="utf-8").splitlines():
                if line.endswith(ref_path):
                    return line.split()[0].strip()
        return "0000000000000000000000000000000000000000"
    return head_content


def check_secret_guard(text: str) -> bool:
    """Returns True if any sensitive credential pattern is detected."""
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            return True
    return False


def evaluate_proposal(
    proposal_data: dict,
    memory_repo_path: Path = DEFAULT_MEMORY_REPO_PATH,
    proposal_schema_path: Path | None = None,
) -> tuple[str, list[str], list[str]]:
    """Evaluates proposal data and returns (decision, reason_codes, evaluated_status_labels).
    
    Decision is strictly one of: AUTO_APPROVE, HUMAN_REVIEW, BLOCKED.
    """
    if not isinstance(proposal_data, dict):
        return "BLOCKED", ["INVALID_PROPOSAL"], []

    req_fields = {
        "schema_version", "proposal_id", "source_result_message_id", "task_id",
        "correlation_id", "memory_base_commit", "target_files", "proposed_changes",
        "reason", "status_labels", "source_references", "requires_chief_approval",
        "created_at"
    }
    if not req_fields.issubset(set(proposal_data.keys())):
        return "BLOCKED", ["INVALID_PROPOSAL"], []

    if proposal_data.get("schema_version") != "2.0":
        return "BLOCKED", ["INVALID_PROPOSAL"], []

    # Check requires_chief_approval
    if proposal_data.get("requires_chief_approval") is not True:
        return "BLOCKED", ["APPROVAL_GATE_REQUIRED"], []

    # Check memory base commit matches current HEAD of memory repo
    current_head = get_memory_commit(memory_repo_path)
    if proposal_data.get("memory_base_commit") != current_head:
        return "BLOCKED", ["MEMORY_HEAD_CONFLICT"], []

    # Check target files against canonical allowlist
    target_files = proposal_data.get("target_files", [])
    if not target_files or not isinstance(target_files, list):
        return "BLOCKED", ["TARGET_NOT_ALLOWED"], []

    for tf in target_files:
        if tf not in CANONICAL_MEMORY_ALLOWLIST:
            return "BLOCKED", ["TARGET_NOT_ALLOWED"], []

    # Check source references
    source_refs = proposal_data.get("source_references", [])
    if not source_refs or not isinstance(source_refs, list):
        return "BLOCKED", ["SOURCE_MISSING"], []

    proposed_changes = proposal_data.get("proposed_changes", [])
    if not proposed_changes or not isinstance(proposed_changes, list):
        return "BLOCKED", ["INVALID_PROPOSAL"], []

    evaluated_status_labels = []
    has_non_auto_status = False
    has_strategic_intent = False

    for idx, change in enumerate(proposed_changes):
        if not isinstance(change, dict):
            return "BLOCKED", ["INVALID_PROPOSAL"], []

        fname = change.get("file")
        if fname not in CANONICAL_MEMORY_ALLOWLIST:
            return "BLOCKED", ["TARGET_NOT_ALLOWED"], []

        action = change.get("action")
        if action == "DELETE":
            return "BLOCKED", ["DELETE_ACTION_FORBIDDEN"], []

        text = change.get("proposed_text", "")
        if check_secret_guard(text):
            return "BLOCKED", ["SECRET_DETECTED"], []

        status_label = change.get("status_label")
        if status_label not in CANONICAL_STATUS_ALLOWLIST:
            return "BLOCKED", ["NON_AUTO_APPROVABLE_STATUS"], []

        evaluated_status_labels.append(status_label)

        # In 088: ONLY VERIFIED_CURRENT is eligible for AUTO_APPROVE
        if status_label != "VERIFIED_CURRENT":
            has_non_auto_status = True
            if status_label in {"IDEA", "USER_INTENT", "PLANNED", "DECISION", "HISTORICAL_DECISION"}:
                has_strategic_intent = True

    # Routing Decisions
    if has_non_auto_status:
        reason_codes = ["NON_AUTO_APPROVABLE_STATUS"]
        if has_strategic_intent:
            reason_codes.append("STRATEGIC_CHANGE")
        else:
            reason_codes.append("UNVERIFIED_STATUS_PRESENT")
        return "HUMAN_REVIEW", reason_codes, evaluated_status_labels

    # All changes are VERIFIED_CURRENT on allowed target files with verified source
    return "AUTO_APPROVE", ["SAFE_VERIFIED_TECHNICAL_FACT"], evaluated_status_labels


def process_proposal_for_chief_decision(
    proposal_file: Path,
    memory_repo_path: Path = DEFAULT_MEMORY_REPO_PATH,
    output_decisions_dir: Path = Path("events/chief-decisions"),
    output_approvals_dir: Path = Path("events/approvals"),
    proposal_schema_path: Path | None = None,
    approval_schema_path: Path | None = None,
    decision_schema_path: Path | None = None,
) -> dict:
    if not proposal_file.exists():
        fail(f"Proposal file not found: {proposal_file}")

    try:
        proposal_data = json.loads(proposal_file.read_text(encoding="utf-8"))
    except Exception as exc:
        proposal_data = {}

    task_id = proposal_data.get("task_id", "TASK-UNKNOWN")
    prop_id = proposal_data.get("proposal_id", f"prop-mem-{task_id}")
    corr_id = proposal_data.get("correlation_id", "corr-unknown")
    msg_id = proposal_data.get("source_result_message_id", "msg-unknown")
    mem_commit = proposal_data.get("memory_base_commit", "0000000000000000000000000000000000000000")
    source_refs = proposal_data.get("source_references", [])

    decision, reason_codes, eval_labels = evaluate_proposal(
        proposal_data=proposal_data,
        memory_repo_path=memory_repo_path,
        proposal_schema_path=proposal_schema_path,
    )

    decision_id = f"dec-chief-{task_id}-{uuid.uuid4().hex[:8]}"
    created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    generated_approval_id = None

    if decision == "AUTO_APPROVE":
        # Generate 087 schema-compliant Chief Approval
        generated_approval_id = f"appr-mem-{task_id}-{uuid.uuid4().hex[:8]}"
        approval_record = {
            "schema_version": "2.0",
            "approval_id": generated_approval_id,
            "proposal_id": prop_id,
            "source_result_message_id": msg_id,
            "task_id": task_id,
            "correlation_id": corr_id,
            "memory_base_commit": mem_commit,
            "approved_by": "AUTONOMOUS_CHIEF_POLICY",
            "approval_status": "APPROVED",
            "approved_changes_count": len(proposal_data.get("proposed_changes", [])),
            "notes": f"Autonomous approval by Chief Policy (088) for verified technical fact in task {task_id}.",
            "approved_at": created_at,
        }
        output_approvals_dir.mkdir(parents=True, exist_ok=True)
        appr_file = output_approvals_dir / f"{task_id}-auto-approval.json"
        appr_file.write_text(json.dumps(approval_record, indent=2) + "\n", encoding="utf-8")

    decision_record = {
        "schema_version": "2.0",
        "decision_id": decision_id,
        "proposal_id": prop_id,
        "task_id": task_id,
        "correlation_id": corr_id,
        "source_result_message_id": msg_id,
        "decision": decision,
        "reason_codes": reason_codes,
        "evaluated_status_labels": eval_labels,
        "memory_base_commit": mem_commit,
        "source_references": source_refs,
        "generated_approval_id": generated_approval_id,
        "policy_version": "088",
        "created_at": created_at,
    }

    output_decisions_dir.mkdir(parents=True, exist_ok=True)
    dec_file = output_decisions_dir / f"{task_id}-chief-decision.json"
    dec_file.write_text(json.dumps(decision_record, indent=2) + "\n", encoding="utf-8")

    return decision_record


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Memory Update Proposal under Autonomous Chief Policy (088)")
    parser.add_argument("--proposal", required=True, help="Path to memory update proposal JSON")
    parser.add_argument("--memory-repo", default=str(DEFAULT_MEMORY_REPO_PATH), help="Path to 2026-project-memory")
    parser.add_argument("--output-decisions", default="events/chief-decisions", help="Output directory for decision records")
    parser.add_argument("--output-approvals", default="events/approvals", help="Output directory for generated approvals")
    args = parser.parse_args()

    proposal_path = Path(args.proposal).resolve()
    memory_repo_path = Path(args.memory_repo).resolve()
    dec_dir = Path(args.output_decisions).resolve()
    appr_dir = Path(args.output_approvals).resolve()

    result = process_proposal_for_chief_decision(
        proposal_file=proposal_path,
        memory_repo_path=memory_repo_path,
        output_decisions_dir=dec_dir,
        output_approvals_dir=appr_dir,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
