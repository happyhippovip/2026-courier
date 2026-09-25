#!/usr/bin/env python3
"""Deterministic Memory Write Handler with Strict Chief Approval Gate.

Applies schema-validated MemoryUpdateProposals to canonical project memory
ONLY when authorized by an explicit, schema-validated MemoryUpdateApproval.

Guarantees:
1. Zero direct writes from RESULT (086 cannot be bypassed).
2. Zero writes without valid, matching Chief Approval.
3. Strict check against dynamic memory base commit (stops on conflict).
4. Strict enforcement of canonical memory target file allowlist.
5. Strict enforcement of canonical status label allowlist.
6. Secret Guard: Rejects any credential/token patterns.
7. Dry-Run mode: Simulates exact modifications with zero disk writes.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_MEMORY_REPO_PATH = Path(
    os.environ.get("COURIER_MEMORY_REPO", "/Users/user/Downloads/2026-project-memory")
)
DEFAULT_PROPOSAL_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas/memory_update_proposal.schema.json"
DEFAULT_APPROVAL_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas/memory_update_approval.schema.json"

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
    raise SystemExit(f"MEMORY_WRITE_HANDLER_ERROR: {message}")


def get_memory_commit(repo_path: Path) -> str:
    """Reads git commit hash directly from .git directory without external CLI execution."""
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


def validate_proposal(proposal_data: dict, schema_path: Path | None = None) -> tuple[bool, str]:
    if schema_path is None or not schema_path.exists():
        schema_path = DEFAULT_PROPOSAL_SCHEMA_PATH

    if not isinstance(proposal_data, dict):
        return False, "Proposal data must be a JSON object"

    req_fields = {
        "schema_version", "proposal_id", "source_result_message_id", "task_id",
        "correlation_id", "memory_base_commit", "target_files", "proposed_changes",
        "reason", "status_labels", "source_references", "requires_chief_approval",
        "created_at"
    }
    if set(proposal_data.keys()) != req_fields:
        return False, f"Proposal field mismatch: expected {req_fields}, got {set(proposal_data.keys())}"

    if proposal_data.get("schema_version") != "2.0":
        return False, f"Invalid schema_version: {proposal_data.get('schema_version')}"

    if proposal_data.get("requires_chief_approval") is not True:
        return False, "Proposal requires_chief_approval must be strictly True"

    if not re.match(r"^prop-mem-[A-Za-z0-9_.-]+$", str(proposal_data.get("proposal_id", ""))):
        return False, f"Invalid proposal_id format: {proposal_data.get('proposal_id')}"

    if not re.match(r"^[0-9a-fA-F]{7,40}$", str(proposal_data.get("memory_base_commit", ""))):
        return False, f"Invalid memory_base_commit: {proposal_data.get('memory_base_commit')}"

    return True, "VALID"


def validate_approval(approval_data: dict, schema_path: Path | None = None) -> tuple[bool, str]:
    if schema_path is None or not schema_path.exists():
        schema_path = DEFAULT_APPROVAL_SCHEMA_PATH

    if not isinstance(approval_data, dict):
        return False, "Approval data must be a JSON object"

    req_fields = {
        "schema_version", "approval_id", "proposal_id", "source_result_message_id",
        "task_id", "correlation_id", "memory_base_commit", "approved_by",
        "approval_status", "approved_at"
    }
    if not req_fields.issubset(set(approval_data.keys())):
        return False, f"Approval missing required fields: {req_fields - set(approval_data.keys())}"

    if approval_data.get("schema_version") != "2.0":
        return False, f"Invalid schema_version: {approval_data.get('schema_version')}"

    if not re.match(r"^appr-mem-[A-Za-z0-9_.-]+$", str(approval_data.get("approval_id", ""))):
        return False, f"Invalid approval_id format: {approval_data.get('approval_id')}"

    if not re.match(r"^prop-mem-[A-Za-z0-9_.-]+$", str(approval_data.get("proposal_id", ""))):
        return False, f"Invalid proposal_id format: {approval_data.get('proposal_id')}"

    if approval_data.get("approval_status") != "APPROVED":
        return False, f"Approval status is not APPROVED: {approval_data.get('approval_status')}"

    if not approval_data.get("approved_by"):
        return False, "approved_by must not be empty"

    return True, "VALID"


def check_secret_guard(text: str) -> bool:
    """Returns True if any sensitive credential pattern is detected."""
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            return True
    return False


def apply_memory_update_proposal(
    proposal_file: Path,
    approval_file: Path,
    memory_repo_path: Path = DEFAULT_MEMORY_REPO_PATH,
    dry_run: bool = False,
    proposal_schema_path: Path | None = None,
    approval_schema_path: Path | None = None,
) -> dict:
    if not proposal_file.exists():
        fail(f"Proposal file not found: {proposal_file}")
    if not approval_file.exists():
        fail(f"Approval file not found: {approval_file}")

    try:
        proposal_data = json.loads(proposal_file.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Failed to parse proposal JSON: {exc}")

    try:
        approval_data = json.loads(approval_file.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Failed to parse approval JSON: {exc}")

    # 1. Validate Proposal
    prop_valid, prop_err = validate_proposal(proposal_data, proposal_schema_path)
    if not prop_valid:
        fail(f"Proposal schema validation failed: {prop_err}")

    # 2. Validate Approval
    appr_valid, appr_err = validate_approval(approval_data, approval_schema_path)
    if not appr_valid:
        fail(f"Approval schema validation failed: {appr_err}")

    # 3. Check Approval <-> Proposal Exact Binding
    if approval_data["proposal_id"] != proposal_data["proposal_id"]:
        fail(f"BLOCKED: Approval proposal_id ({approval_data['proposal_id']}) does not match Proposal proposal_id ({proposal_data['proposal_id']})")

    if approval_data["source_result_message_id"] != proposal_data["source_result_message_id"]:
        fail(f"BLOCKED: Approval source_result_message_id ({approval_data['source_result_message_id']}) does not match Proposal ({proposal_data['source_result_message_id']})")

    if approval_data["task_id"] != proposal_data["task_id"]:
        fail(f"BLOCKED: Approval task_id ({approval_data['task_id']}) does not match Proposal task_id ({proposal_data['task_id']})")

    if approval_data["correlation_id"] != proposal_data["correlation_id"]:
        fail(f"BLOCKED: Approval correlation_id ({approval_data['correlation_id']}) does not match Proposal correlation_id ({proposal_data['correlation_id']})")

    if approval_data["memory_base_commit"] != proposal_data["memory_base_commit"]:
        fail(f"BLOCKED: Approval memory_base_commit ({approval_data['memory_base_commit']}) does not match Proposal memory_base_commit ({proposal_data['memory_base_commit']})")

    # 4. Check Current Memory Repository HEAD Commit (Conflict Detection)
    current_head = get_memory_commit(memory_repo_path)
    if current_head != proposal_data["memory_base_commit"]:
        fail(f"CONFLICT: Current memory HEAD commit ({current_head}) does not match Proposal memory_base_commit ({proposal_data['memory_base_commit']}). Re-proposal required.")

    # 5. Check Target Files against Canonical Allowlist
    for target_file in proposal_data.get("target_files", []):
        if target_file not in CANONICAL_MEMORY_ALLOWLIST:
            fail(f"BLOCKED: Target file '{target_file}' is not in the canonical memory allowlist ({sorted(CANONICAL_MEMORY_ALLOWLIST)})")

    # 6. Check Proposed Changes (Allowlist, Status Allowlist, Secret Guard)
    proposed_changes = proposal_data.get("proposed_changes", [])
    if not proposed_changes:
        fail("BLOCKED: Proposed changes list is empty")

    for idx, change in enumerate(proposed_changes):
        fname = change.get("file")
        if fname not in CANONICAL_MEMORY_ALLOWLIST:
            fail(f"BLOCKED: Change #{idx} targets non-canonical file '{fname}'")

        status_label = change.get("status_label")
        if status_label not in CANONICAL_STATUS_ALLOWLIST:
            fail(f"BLOCKED: Change #{idx} contains non-canonical status label '{status_label}'")

        text = change.get("proposed_text", "")
        if check_secret_guard(text):
            fail(f"BLOCKED: Change #{idx} contains sensitive credential/secret pattern")

    # 7. Execution (Dry-Run vs Real Write)
    applied_changes = []
    files_modified = set()

    for idx, change in enumerate(proposed_changes):
        target_path = memory_repo_path / change["file"]
        if not target_path.exists():
            fail(f"BLOCKED: Target memory file does not exist: {target_path}")

        current_content = target_path.read_text(encoding="utf-8")
        section = change["section"]
        text_to_apply = change["proposed_text"].strip()
        action = change.get("action", "APPEND")

        if dry_run:
            applied_changes.append({
                "file": change["file"],
                "section": section,
                "action": action,
                "status_label": change["status_label"],
                "text": text_to_apply,
                "simulated": True,
            })
            files_modified.add(change["file"])
        else:
            # Idempotent retry: exact text already present -> skip, never duplicate.
            if text_to_apply in current_content:
                applied_changes.append({
                    "file": change["file"],
                    "section": section,
                    "action": action,
                    "status_label": change["status_label"],
                    "text": text_to_apply,
                    "skipped_duplicate": True,
                })
                continue
            # Perform atomic section append via tmp + replace so a crash
            # cannot leave a truncated memory file behind.
            if f"## {section}" in current_content or f"# {section}" in current_content:
                # Append directly under section
                new_content = current_content.rstrip() + f"\n\n{text_to_apply}\n"
            else:
                # Append section with content at EOF
                new_content = current_content.rstrip() + f"\n\n## {section}\n\n{text_to_apply}\n"

            tmp_path = target_path.with_name(target_path.name + ".tmp")
            tmp_path.write_text(new_content, encoding="utf-8")
            os.replace(tmp_path, target_path)

            # Post-write verification: re-read file
            verified_content = target_path.read_text(encoding="utf-8")
            if text_to_apply not in verified_content:
                fail(f"Verification failed: text not found after write in {change['file']}")

            applied_changes.append({
                "file": change["file"],
                "section": section,
                "action": action,
                "status_label": change["status_label"],
                "text": text_to_apply,
                "verified": True,
            })
            files_modified.add(change["file"])

    result_data = {
        "status": "DRY_RUN_PASS" if dry_run else "APPLIED_PASS",
        "proposal_id": proposal_data["proposal_id"],
        "approval_id": approval_data["approval_id"],
        "approved_by": approval_data["approved_by"],
        "task_id": proposal_data["task_id"],
        "memory_base_commit": proposal_data["memory_base_commit"],
        "files_modified_count": len(files_modified),
        "files_modified": sorted(files_modified),
        "changes_applied_count": len(applied_changes),
        "applied_changes": applied_changes,
        "dry_run": dry_run,
        "executed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    return result_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Chief-Approved Memory Update Proposal to Canonical Project Memory")
    parser.add_argument("--proposal", required=True, help="Path to memory update proposal JSON")
    parser.add_argument("--approval", required=True, help="Path to chief approval JSON")
    parser.add_argument("--memory-repo", default=str(DEFAULT_MEMORY_REPO_PATH), help="Path to 2026-project-memory")
    parser.add_argument("--dry-run", action="store_true", help="Simulate changes without writing to memory files")
    parser.add_argument("--proposal-schema", help="Custom proposal schema path")
    parser.add_argument("--approval-schema", help="Custom approval schema path")
    args = parser.parse_args()

    proposal_path = Path(args.proposal).resolve()
    approval_path = Path(args.approval).resolve()
    memory_repo_path = Path(args.memory_repo).resolve()
    prop_schema = Path(args.proposal_schema).resolve() if args.proposal_schema else None
    appr_schema = Path(args.approval_schema).resolve() if args.approval_schema else None

    result = apply_memory_update_proposal(
        proposal_file=proposal_path,
        approval_file=approval_path,
        memory_repo_path=memory_repo_path,
        dry_run=args.dry_run,
        proposal_schema_path=prop_schema,
        approval_schema_path=appr_schema,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
