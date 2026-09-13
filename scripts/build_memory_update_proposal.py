#!/usr/bin/env python3
"""Deterministic Builder and Validator for Memory Update Proposals.

Constructs schema-validated proposals for canonical project memory updates
derived strictly from verified Antigravity results.
Guarantees that:
1. 2026-project-memory remains strictly read-only.
2. requires_chief_approval is always true.
3. memory_base_commit is dynamically extracted from 2026-project-memory.
4. Non-current or unverified states are never promoted to VERIFIED_CURRENT.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

DEFAULT_MEMORY_REPO_PATH = Path("/Users/user/Downloads/2026-project-memory")
DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas/memory_update_proposal.schema.json"
ZERO_COMMIT = "0" * 40
FULL_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40}$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def fail(message: str) -> None:
    raise SystemExit(f"MEMORY_PROPOSAL_ERROR: {message}")


def atomic_write_json(path: Path, payload: dict) -> None:
    """Replace a proposal artifact without leaving a truncated JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.tmp.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            # The replacement remains atomic even where directory fsync is unavailable.
            pass
    finally:
        if temp_path.exists():
            temp_path.unlink()


def atomic_create_json(path: Path, payload: dict) -> bool:
    """Create a new immutable artifact, returning False if it already exists.

    ``os.link`` is an atomic destination-creation primitive when both names are
    in the same directory.  It prevents two initial creators from each passing
    an ``exists`` check and silently overwriting one another.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.tmp.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp_path, path)
        except FileExistsError:
            return False
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            # Creation remains atomic where directory fsync is unavailable.
            pass
        return True
    finally:
        if temp_path.exists():
            temp_path.unlink()


def load_matching_proposal(path: Path, proposal_id: str, schema_path: Path | None) -> dict:
    """Load an existing immutable proposal or fail closed on mismatch/corruption."""
    try:
        existing_proposal = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"Existing proposal artifact is unreadable: {exc}")
    if not isinstance(existing_proposal, dict):
        fail("Existing proposal artifact must be a JSON object")
    if existing_proposal.get("proposal_id") != proposal_id:
        fail(f"Proposal collision for task_id {path.stem.removesuffix('-memory-proposal')}; existing artifact has a different immutable source")
    existing_valid, existing_error = validate_proposal_against_schema(existing_proposal, schema_path)
    if not existing_valid:
        fail(f"Existing proposal artifact is invalid: {existing_error}")
    return existing_proposal


def get_memory_commit(repo_path: Path) -> str:
    """Read a validated HEAD from either a Git directory or worktree pointer.

    Git worktrees use a ``.git`` *file* that points to their real gitdir.  The
    old directory-only implementation crashed in that ordinary layout, which
    left a proposal without a trustworthy base checkpoint.
    """
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        return ZERO_COMMIT

    try:
        if git_dir.is_file():
            pointer = git_dir.read_text(encoding="utf-8").strip()
            if not pointer.startswith("gitdir:"):
                return ZERO_COMMIT
            location = pointer[len("gitdir:"):].strip()
            if not location:
                return ZERO_COMMIT
            candidate = Path(location)
            git_dir = (git_dir.parent / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        if not git_dir.is_dir():
            return ZERO_COMMIT

        head_file = git_dir / "HEAD"
        if not head_file.is_file():
            return ZERO_COMMIT

        head_content = head_file.read_text(encoding="utf-8").strip()
        if head_content.startswith("ref:"):
            ref_path = head_content[4:].strip()
            if not ref_path or Path(ref_path).is_absolute() or ".." in Path(ref_path).parts:
                return ZERO_COMMIT
            ref_file = git_dir / ref_path
            if ref_file.is_file():
                candidate_commit = ref_file.read_text(encoding="utf-8").strip()
                return candidate_commit.lower() if FULL_COMMIT_RE.fullmatch(candidate_commit) else ZERO_COMMIT
            packed_refs_file = git_dir / "packed-refs"
            if packed_refs_file.is_file():
                for line in packed_refs_file.read_text(encoding="utf-8").splitlines():
                    parts = line.split()
                    if len(parts) == 2 and parts[1] == ref_path and FULL_COMMIT_RE.fullmatch(parts[0]):
                        return parts[0].lower()
            return ZERO_COMMIT
        return head_content.lower() if FULL_COMMIT_RE.fullmatch(head_content) else ZERO_COMMIT
    except (OSError, UnicodeDecodeError):
        return ZERO_COMMIT


def validate_proposal_against_schema(proposal_data: dict, schema_path: Path | None = None) -> tuple[bool, str]:
    """Validates memory update proposal data strictly against schemas/memory_update_proposal.schema.json."""
    if schema_path is None or not schema_path.exists():
        schema_path = DEFAULT_SCHEMA_PATH

    schema = None
    if schema_path and schema_path.exists():
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return False, f"Failed to load schema file {schema_path}: {exc}"

    req_fields = set(schema.get("required", [])) if schema else {
        "schema_version", "proposal_id", "source_result_message_id", "task_id",
        "correlation_id", "memory_base_commit", "target_files", "proposed_changes",
        "reason", "status_labels", "source_references", "requires_chief_approval",
        "created_at"
    }

    if not isinstance(proposal_data, dict):
        return False, "Proposal data must be a JSON object"

    if set(proposal_data.keys()) != req_fields:
        return False, f"Field mismatch: expected {req_fields}, got {set(proposal_data.keys())}"

    if proposal_data.get("schema_version") != "2.0":
        return False, f"Invalid schema_version: {proposal_data.get('schema_version')} (expected '2.0')"

    if not re.match(r"^prop-mem-[A-Za-z0-9_.-]+$", str(proposal_data.get("proposal_id", ""))):
        return False, f"Invalid proposal_id pattern: {proposal_data.get('proposal_id')}"

    for field in ("source_result_message_id", "task_id", "correlation_id"):
        value = proposal_data.get(field)
        if not isinstance(value, str) or not IDENTIFIER_RE.fullmatch(value):
            return False, f"Invalid {field} pattern: {value}"

    if not re.match(r"^[0-9a-fA-F]{7,40}$", str(proposal_data.get("memory_base_commit", ""))):
        return False, f"Invalid memory_base_commit: {proposal_data.get('memory_base_commit')}"

    if proposal_data.get("requires_chief_approval") is not True:
        return False, "requires_chief_approval must be strictly boolean True"

    target_files = proposal_data.get("target_files")
    if not isinstance(target_files, list) or not target_files or not all(isinstance(x, str) for x in target_files):
        return False, "target_files must be a non-empty list of strings"

    for field in ("reason", "created_at"):
        if not isinstance(proposal_data.get(field), str) or not proposal_data[field]:
            return False, f"{field} must be a non-empty string"

    for field in ("status_labels", "source_references"):
        value = proposal_data.get(field)
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
            return False, f"{field} must be a non-empty list of non-empty strings"

    changes = proposal_data.get("proposed_changes")
    if not isinstance(changes, list) or not changes:
        return False, "proposed_changes must be a non-empty list"

    allowed_actions = {"APPEND", "UPDATE", "INSERT", "FLAG_STATUS"}
    allowed_status = {
        "VERIFIED_CURRENT", "EXTERNAL_STATUS", "HISTORICAL_DECISION", "PLANNED",
        "IDEA", "CONFLICT", "UNKNOWN", "STATUS_BOUNDARY", "PAUSED",
        "PAUSED_EXTERNAL_GATE", "DEFERRED", "NOT VERIFIED", "IN PROGRESS"
    }

    for idx, ch in enumerate(changes):
        if not isinstance(ch, dict):
            return False, f"Change #{idx} must be an object"
        ch_req = {"file", "action", "section", "proposed_text", "status_label"}
        if set(ch.keys()) != ch_req:
            return False, f"Change #{idx} fields mismatch: expected {ch_req}, got {set(ch.keys())}"
        if ch.get("action") not in allowed_actions:
            return False, f"Change #{idx} invalid action: {ch.get('action')}"
        if ch.get("status_label") not in allowed_status:
            return False, f"Change #{idx} invalid status_label: {ch.get('status_label')}"
        if not isinstance(ch.get("file"), str) or not ch["file"]:
            return False, f"Change #{idx} file must be a non-empty string"
        if not isinstance(ch.get("section"), str) or not ch["section"]:
            return False, f"Change #{idx} section must be a non-empty string"
        if not ch.get("proposed_text") or not isinstance(ch.get("proposed_text"), str):
            return False, f"Change #{idx} proposed_text must be a non-empty string"

    return True, "VALID"


def build_proposal_from_result(
    result_file: Path,
    memory_repo_path: Path = DEFAULT_MEMORY_REPO_PATH,
    output_dir: Path = Path("events/proposals"),
    schema_path: Path | None = None,
    target_files: list[str] | None = None,
    custom_reason: str | None = None,
) -> dict:
    if not result_file.exists():
        fail(f"Result file not found: {result_file}")

    try:
        res_data = json.loads(result_file.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Invalid JSON in result file: {exc}")

    task_id = res_data.get("task_id")
    msg_id = res_data.get("message_id")
    corr_id = res_data.get("correlation_id")

    for field, value in (("task_id", task_id), ("message_id", msg_id), ("correlation_id", corr_id)):
        if not isinstance(value, str) or not IDENTIFIER_RE.fullmatch(value):
            fail(f"Result envelope has invalid {field}")

    payload = res_data.get("payload", {})
    verified_facts = payload.get("verified_facts", [])
    summary = payload.get("summary", "Technical execution completed")

    # Resolve dynamic memory commit from 2026-project-memory
    mem_base_commit = get_memory_commit(memory_repo_path)

    # Derive target files if not specified
    if not target_files:
        target_files = ["TECHNICAL_CONTEXT.md"]

    # Build proposed changes derived from verified facts
    proposed_changes = []
    status_labels = set()
    today_str = datetime.date.today().isoformat()

    for fact in verified_facts:
        fact_str = str(fact)
        # Determine status label: preserve UNVERIFIED / EXTERNAL_STATUS / CONFLICT
        if any(w in fact_str.upper() for w in ["EXTERNAL", "TIKTOK", "FIVERR", "KLEINANZEIGEN", "REMOTE"]):
            label = "EXTERNAL_STATUS"
        elif any(w in fact_str.upper() for w in ["CONFLICT", "DISCREPANCY", "MISMATCH"]):
            label = "CONFLICT"
        elif any(w in fact_str.upper() for w in ["UNKNOWN", "MISSING", "UNRESOLVED"]):
            label = "UNKNOWN"
        elif any(w in fact_str.upper() for w in ["PAUSED", "GATE"]):
            label = "PAUSED_EXTERNAL_GATE"
        else:
            label = "VERIFIED_CURRENT"

        status_labels.add(label)
        change_entry = {
            "file": target_files[0],
            "action": "APPEND",
            "section": "Current verified local technical state",
            "proposed_text": f"- **{label}** | Source: verified Antigravity execution `{msg_id}` | Verified: {today_str}. {fact_str}",
            "status_label": label,
        }
        proposed_changes.append(change_entry)

    if not proposed_changes:
        # Fallback single change from summary
        label = "VERIFIED_CURRENT"
        status_labels.add(label)
        proposed_changes.append({
            "file": target_files[0],
            "action": "APPEND",
            "section": "Current verified local technical state",
            "proposed_text": f"- **{label}** | Source: verified Antigravity execution `{msg_id}` | Verified: {today_str}. {summary}",
            "status_label": label,
        })

    reason = custom_reason or f"Record verified facts from Antigravity task execution {task_id} ({summary})"
    # Replays of the same immutable result must have one semantic proposal,
    # rather than creating fresh approval targets through a random UUID.
    source_fingerprint = hashlib.sha256(
        json.dumps(res_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    proposal_id = f"prop-mem-{task_id}-{source_fingerprint[:16]}"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{task_id}-memory-proposal.json"
    existing_proposal = None

    # A retry of the exact immutable result must be byte-stable.  Conversely,
    # a different result cannot silently replace the existing approval target
    # merely because it reuses the same task id.
    if out_file.exists():
        existing_proposal = load_matching_proposal(out_file, proposal_id, schema_path)
        return existing_proposal

    created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    canonical_order = [
        "VERIFIED_CURRENT", "EXTERNAL_STATUS", "HISTORICAL_DECISION", "PLANNED",
        "IDEA", "CONFLICT", "UNKNOWN", "STATUS_BOUNDARY", "PAUSED",
        "PAUSED_EXTERNAL_GATE", "DEFERRED", "NOT VERIFIED", "IN PROGRESS"
    ]
    ordered_labels = [l for l in canonical_order if l in status_labels]

    proposal = {
        "schema_version": "2.0",
        "proposal_id": proposal_id,
        "source_result_message_id": msg_id,
        "task_id": task_id,
        "correlation_id": corr_id,
        "memory_base_commit": mem_base_commit,
        "target_files": list(target_files),
        "proposed_changes": proposed_changes,
        "reason": reason,
        "status_labels": ordered_labels,
        "source_references": [result_file.name] + list(target_files),
        "requires_chief_approval": True,
        "created_at": created_at,
    }

    # Strict JSON schema validation
    is_valid, err = validate_proposal_against_schema(proposal, schema_path)
    if not is_valid:
        fail(f"Generated proposal failed schema validation: {err}")

    if atomic_create_json(out_file, proposal):
        return proposal

    # Another process won the initial claim after our pre-check.  Its result
    # must be the exact same immutable proposal, otherwise deny the collision.
    return load_matching_proposal(out_file, proposal_id, schema_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and Validate Memory Update Proposal from Antigravity Result")
    parser.add_argument("--result", help="Path to Antigravity result JSON")
    parser.add_argument("--memory-repo", default=str(DEFAULT_MEMORY_REPO_PATH), help="Path to 2026-project-memory")
    parser.add_argument("--output-dir", default="events/proposals", help="Output directory for proposals")
    parser.add_argument("--validate-proposal", help="Validate an existing proposal file against the JSON Schema")
    parser.add_argument("--schema", help="Custom path to memory_update_proposal.schema.json")
    args = parser.parse_args()

    schema_path = Path(args.schema).resolve() if args.schema else None

    if args.validate_proposal:
        prop_file = Path(args.validate_proposal)
        if not prop_file.exists():
            fail(f"Proposal file not found: {prop_file}")
        try:
            prop_data = json.loads(prop_file.read_text(encoding="utf-8"))
        except Exception as exc:
            fail(f"Invalid JSON in proposal file: {exc}")
        valid, msg = validate_proposal_against_schema(prop_data, schema_path)
        if not valid:
            fail(f"Proposal validation failed: {msg}")
        print(f"MEMORY_UPDATE_PROPOSAL_SCHEMA_VALID: {prop_file.name}")
        return

    if not args.result:
        fail("Missing required --result argument")

    result_path = Path(args.result)
    memory_repo_path = Path(args.memory_repo).resolve()
    output_dir = Path(args.output_dir)

    proposal = build_proposal_from_result(
        result_file=result_path,
        memory_repo_path=memory_repo_path,
        output_dir=output_dir,
        schema_path=schema_path,
    )
    print(f"MEMORY_UPDATE_PROPOSAL_CREATED: id={proposal['proposal_id']}, task={proposal['task_id']}, src_res={proposal['source_result_message_id']}")


if __name__ == "__main__":
    main()
