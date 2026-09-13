#!/usr/bin/env python3
"""Local, file/event-only ingress for the Thought Memory Mesh.

Original inbox files are never modified or deleted. Runtime records are
atomically written under git-ignored paths. The adapter has no network,
OAuth, Slack, ChatGPT, Google, or Project-Memory write behavior.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from run_thought_memory_mesh import INITIAL_ANCHOR, canonical_hash, contains_sensitive_value, parse_timestamp, run_mesh

SUPPORTED_REAL_SOURCES = {"CHAT_EXPORT", "COURIER_EVENT", "WORK_RESULT", "GOOGLE_ANTIGRAVITY_RESULT"}
REQUIRED_FIELDS = {"ingestion_id", "source_type", "source_message_id", "source_timestamp", "received_at", "content_hash", "content", "metadata", "correlation_id", "privacy_class"}


class IngestionRecoveryError(RuntimeError):
    """A durable ingestion record is malformed or contradicts its journal."""


def atomic_json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        # Best effort only: Windows does not support opening a directory as a
        # file descriptor.  The replaced file remains valid either way.
        try:
            directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            directory_fd = os.open(path.parent, directory_flags)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_recovery_json(path: Path, record_kind: str) -> Any:
    """Load a recovery authority without turning corruption into an empty state."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IngestionRecoveryError(f"{record_kind} unreadable: {path.name}") from error


def safe_rejection(path: Path, ingestion_id: str | None, reason: str) -> None:
    atomic_json_write(path, {"ingestion_id": ingestion_id, "status": "REJECTED", "reason": reason})


def validate_envelope(data: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(data, dict) or set(data) != REQUIRED_FIELDS:
        return None, "invalid envelope fields"
    try:
        if not all(isinstance(data[key], str) and data[key] for key in ("ingestion_id", "source_message_id", "correlation_id", "content_hash")):
            return None, "missing identity field"
        if data["source_type"] not in SUPPORTED_REAL_SOURCES:
            return None, "unsupported real source"
        if data["privacy_class"] == "SENSITIVE":
            return None, "sensitive privacy class"
        if data["privacy_class"] not in {"PUBLIC", "INTERNAL", "SENSITIVE"}:
            return None, "invalid privacy class"
        if not isinstance(data["metadata"], dict) or not isinstance(data["content"], (str, dict)):
            return None, "invalid content or metadata"
        parse_timestamp(data["source_timestamp"])
        parse_timestamp(data["received_at"])
        if canonical_hash(data["content"]) != data["content_hash"]:
            return None, "content_hash mismatch"
        if contains_sensitive_value(data["content"]) or contains_sensitive_value(data["metadata"]):
            return None, "sensitive content rejected"
    except (TypeError, ValueError):
        return None, "invalid timestamp or content"
    return data, None


def normalize(envelope: dict[str, Any]) -> dict[str, Any]:
    content = envelope["content"]
    metadata = envelope["metadata"]
    summary = content if isinstance(content, str) else str(content.get("summary", "")).strip()
    payload = {
        "kind": str(metadata.get("kind", "OPEN_QUESTION")),
        "summary": summary,
        "status_label": str(metadata.get("status_label", "UNKNOWN")),
    }
    if "requested_status" in metadata:
        payload["requested_status"] = str(metadata["requested_status"])
    return {
        "schema_version": "thought-message-1.0",
        "message_id": envelope["source_message_id"],
        "timestamp": envelope["source_timestamp"],
        "source": envelope["source_type"],
        "payload": payload,
        "payload_hash": canonical_hash(payload),
    }


def load_recoverable_state(state_path: Path, processed_dir: Path) -> dict[str, Any]:
    state = (
        {"ingestions": {}, "source_messages": {}, "coverage_ledger": {}}
        if not state_path.exists()
        else load_recovery_json(state_path, "ingestion state")
    )
    if not isinstance(state, dict) or not all(isinstance(state.get(key), dict) for key in (
        "ingestions", "source_messages", "coverage_ledger",
    )):
        raise IngestionRecoveryError("ingestion state has invalid structure")
    for run_file in sorted(processed_dir.glob("run-*.json")):
        record = load_recovery_json(run_file, "ingestion run record")
        if not isinstance(record, dict) or not isinstance(record.get("completed_ingestions"), list):
            raise IngestionRecoveryError(f"ingestion run record has invalid structure: {run_file.name}")
        for item in record["completed_ingestions"]:
            if not isinstance(item, dict) or not all(isinstance(item.get(key), str) and item[key] for key in (
                "ingestion_id", "source_message_id", "content_hash",
            )):
                raise IngestionRecoveryError(f"ingestion run record has invalid identity: {run_file.name}")
            for index_name, identity in (("ingestions", item["ingestion_id"]), ("source_messages", item["source_message_id"])):
                known = state[index_name].get(identity)
                if known is not None and known != item["content_hash"]:
                    raise IngestionRecoveryError(f"conflicting {index_name} recovery identity: {identity}")
                state[index_name].setdefault(identity, item["content_hash"])
        if record.get("coverage_ledger"):
            if not isinstance(record["coverage_ledger"], dict):
                raise IngestionRecoveryError(f"ingestion run record has invalid coverage ledger: {run_file.name}")
            state["coverage_ledger"] = record["coverage_ledger"]
    return state


def _run_ingestion(inbox: Path, processed: Path, rejected: Path, memory_repo: Path) -> dict[str, Any]:
    state_path = processed / "ingestion-state.json"
    state = load_recoverable_state(state_path, processed)
    accepted: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
    new_ingestions: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
    rejected_count = skipped_count = conflict_count = 0
    batch_ids: dict[str, str] = {}
    batch_sources: dict[str, str] = {}
    for input_file in sorted(inbox.glob("*.json")):
        try:
            # Force UTF-8 explicitly; fail-closed if invalid
            raw_text = input_file.read_bytes().decode("utf-8")
            raw = json.loads(raw_text)
        except UnicodeDecodeError:
            safe_rejection(rejected / f"{input_file.stem}-rejected.json", None, "invalid UTF-8 encoding")
            rejected_count += 1
            continue
        except json.JSONDecodeError:
            safe_rejection(rejected / f"{input_file.stem}-rejected.json", None, "invalid JSON")
            rejected_count += 1
            continue
        envelope, error = validate_envelope(raw)
        safe_id = envelope["ingestion_id"] if envelope else (raw.get("ingestion_id") if isinstance(raw, dict) else None)
        if error:
            safe_rejection(rejected / f"{input_file.stem}-rejected.json", safe_id, error)
            rejected_count += 1
            continue
        assert envelope is not None
        thought = normalize(envelope)
        if not thought["payload"]["summary"]:
            safe_rejection(rejected / f"{input_file.stem}-rejected.json", envelope["ingestion_id"], "empty normalized content")
            rejected_count += 1
            continue
        if parse_timestamp(thought["timestamp"]).date() < dt.date.fromisoformat(INITIAL_ANCHOR):
            safe_rejection(rejected / f"{input_file.stem}-rejected.json", envelope["ingestion_id"], "before historical anchor")
            rejected_count += 1
            continue
        known = state["ingestions"].get(envelope["ingestion_id"])
        if known is not None:
            if known == envelope["content_hash"]:
                skipped_count += 1
                # Keep one normalized historical message in coverage scans, but never process it as delta again.
                if thought["message_id"] not in batch_sources:
                    accepted.append((input_file, envelope, thought))
                    batch_sources[thought["message_id"]] = envelope["content_hash"]
            else:
                safe_rejection(rejected / f"{input_file.stem}-rejected.json", envelope["ingestion_id"], "ingestion id/hash conflict")
                conflict_count += 1
            continue
        if envelope["ingestion_id"] in batch_ids:
            if batch_ids[envelope["ingestion_id"]] == envelope["content_hash"]:
                skipped_count += 1
            else:
                safe_rejection(rejected / f"{input_file.stem}-rejected.json", envelope["ingestion_id"], "in-batch ingestion id/hash conflict")
                conflict_count += 1
            continue
        source_hash = state["source_messages"].get(thought["message_id"])
        if source_hash is not None:
            if source_hash != envelope["content_hash"]:
                safe_rejection(rejected / f"{input_file.stem}-rejected.json", envelope["ingestion_id"], "source message id/hash conflict")
                conflict_count += 1
            else:
                # A source-message id is the immutable source identity.  A
                # duplicate envelope may carry a new ingestion id after a
                # retry/replay, but it must not become a second semantic
                # thought or trigger another mesh/proposal run.
                skipped_count += 1
            continue
        if thought["message_id"] in batch_sources:
            if batch_sources[thought["message_id"]] != envelope["content_hash"]:
                safe_rejection(rejected / f"{input_file.stem}-rejected.json", envelope["ingestion_id"], "in-batch source message id/hash conflict")
                conflict_count += 1
            else:
                # Same source identity and content in one batch is a replay,
                # not a second new thought.
                skipped_count += 1
            continue
        batch_ids[envelope["ingestion_id"]] = envelope["content_hash"]
        batch_sources[thought["message_id"]] = envelope["content_hash"]
        accepted.append((input_file, envelope, thought))
        new_ingestions.append((input_file, envelope, thought))
    if not new_ingestions:
        return {"new_ingestions": 0, "skipped": skipped_count, "rejected": rejected_count, "conflicts": conflict_count, "proposal_created": False, "recovered": bool(state.get("ingestions"))}
    mesh_result = run_mesh([item[2] for item in accepted], state.get("coverage_ledger", {}), memory_repo)
    import hashlib
    def robust_hash(data):
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()

    completed = [{
        "ingestion_id": envelope["ingestion_id"], 
        "content_hash": envelope["content_hash"], 
        "source_message_id": thought["message_id"], 
        "thought_payload_hash": thought["payload_hash"], 
        "correlation_id": envelope["correlation_id"],
        "source_timestamp": envelope.get("source_timestamp"),
        "ingestion_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "original_envelope": envelope
    } for _, envelope, thought in new_ingestions]
    run_id = robust_hash([(item["ingestion_id"], item["content_hash"]) for item in completed])[:16]
    record = {"run_id": run_id, "completed_ingestions": completed, "coverage_ledger": mesh_result["coverage_ledger"], "memory_update_proposal": mesh_result["memory_update_proposal"], "chief_delivery_adapter": mesh_result["chief_delivery_adapter"], "status": "COMPLETED_LOCAL_NOT_DELIVERED"}
    atomic_json_write(processed / f"run-{run_id}.json", record)
    state["ingestions"].update({item["ingestion_id"]: item["content_hash"] for item in completed})
    state["source_messages"].update({item["source_message_id"]: item["content_hash"] for item in completed})
    state["coverage_ledger"] = mesh_result["coverage_ledger"]
    atomic_json_write(state_path, state)
    return {"new_ingestions": len(new_ingestions), "skipped": skipped_count, "rejected": rejected_count, "conflicts": conflict_count, "proposal_created": mesh_result["memory_update_proposal"] is not None, "scene_audit": mesh_result["scene_audit"], "thought_boss_a": mesh_result["thought_boss_a"], "thought_boss_b": mesh_result["thought_boss_b"], "chief_delivery": mesh_result["chief_delivery_adapter"], "run_record": str(processed / f"run-{run_id}.json")}


def run_ingestion(inbox: Path, processed: Path, rejected: Path, memory_repo: Path) -> dict[str, Any]:
    """Serialize local runners. A live/stale lock fails closed rather than risking duplicate proposals."""
    processed.mkdir(parents=True, exist_ok=True)
    lock = processed / ".ingestion.lock"
    try:
        lock.mkdir()
    except FileExistsError:
        return {"status": "LOCKED", "new_ingestions": 0, "proposal_created": False, "retry_safe": True}
    try:
        return _run_ingestion(inbox, processed, rejected, memory_repo)
    except IngestionRecoveryError as error:
        # Do not replace a damaged authority or infer its meaning.  The caller
        # receives a deterministic, retry-safe boundary instead of a traceback
        # or an accidental fresh state.
        return {
            "status": "RECOVERY_STATE_CORRUPT",
            "new_ingestions": 0,
            "proposal_created": False,
            "retry_safe": True,
            "reason": str(error),
        }
    finally:
        lock.rmdir()


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Run local file/event Thought Memory Mesh ingestion")
    parser.add_argument("--inbox", type=Path, default=root / "events/thought-incoming")
    parser.add_argument("--processed", type=Path, default=root / "events/thought-processed")
    parser.add_argument("--rejected", type=Path, default=root / "events/thought-rejected")
    parser.add_argument("--memory-repo", type=Path, default=Path("/Users/user/Downloads/2026-project-memory"))
    args = parser.parse_args()
    print(json.dumps(run_ingestion(args.inbox, args.processed, args.rejected, args.memory_repo), indent=2))


if __name__ == "__main__":
    main()
