#!/usr/bin/env python3
"""Durable, coordination-only handoff ledger with optimistic writer fencing."""

from __future__ import annotations

import argparse
import contextlib
import copy
import errno
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

FORMAT = "courier-agent-handoff-ledger"
SCHEMA_VERSION = 1
NON_AUTHORITY = (
    "Coordination metadata only; this ledger has no scheduler, runtime, "
    "execution, dispatch, verification, or Courier truth authority."
)
RECORD_FIELDS = (
    "PROJECT",
    "GOAL",
    "CURRENT_SHA",
    "BRANCH",
    "RUNTIME_IDENTITY",
    "RUNTIME_OWNER",
    "STATUS",
    "PROVEN_EDGES",
    "UNPROVEN_EDGES",
    "FIRST_CAUSAL_BLOCKER",
    "BLOCKER_OWNER",
    "NEXT_EXECUTABLE_ACTION",
    "ACTIVE_WRITERS",
    "COLLISION_SCOPE",
    "GOALS_SUBMITTED",
    "TASKS_COMPLETED",
    "WORKERS_USED",
    "USER_CONTINUE_MESSAGES",
    "MANUAL_PROCESS_RESTARTS",
    "DUPLICATE_EXTERNAL_EFFECTS",
    "TEMP_TASK_PROCESSES_AFTER_DONE",
    "CLEAN_IDLE",
    "QUEUE_INDEPENDENT",
    "LAST_EVIDENCE",
    "LAST_UPDATED_BY",
    "CONTINUATION_CHECKPOINT",
)
LIST_FIELDS = {
    "PROVEN_EDGES",
    "UNPROVEN_EDGES",
    "ACTIVE_WRITERS",
    "COLLISION_SCOPE",
    "LAST_EVIDENCE",
}
COUNT_FIELDS = {
    "GOALS_SUBMITTED",
    "TASKS_COMPLETED",
    "WORKERS_USED",
    "USER_CONTINUE_MESSAGES",
    "MANUAL_PROCESS_RESTARTS",
    "DUPLICATE_EXTERNAL_EFFECTS",
    "TEMP_TASK_PROCESSES_AFTER_DONE",
}
TRISTATE_FIELDS = {"CLEAN_IDLE", "QUEUE_INDEPENDENT"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SECRET_KEY_RE = re.compile(
    r"(?i)(api.?key|password|passwd|authorization|client.?secret|"
    r"access.?token|refresh.?token|private.?key)"
)
SECRET_VALUE_RE = re.compile(
    r"(?i)(?:api[_ -]?key|password|passwd|authorization|bearer|"
    r"client[_ -]?secret|access[_ -]?token|refresh[_ -]?token|"
    r"private[_ -]?key)\s*[:=]\s*\S+|"
    r"\bbearer\s+\S+|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\bAKIA[A-Z0-9]{16}\b|"
    r"\b(?:github_pat_|gh[pousr]_|sk-)[A-Za-z0-9_-]{16,}"
)


class LedgerError(RuntimeError):
    """Expected fail-closed ledger error."""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        .encode("utf-8")
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def reject_secrets(value: Any, path: str = "record") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if SECRET_KEY_RE.search(str(key)):
                raise LedgerError(f"likely secret field rejected at {path}.{key}")
            reject_secrets(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_secrets(child, f"{path}[{index}]")
    elif isinstance(value, str) and SECRET_VALUE_RE.search(value):
        raise LedgerError(f"likely secret value rejected at {path}")


def _nonempty_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LedgerError(f"{field} must be a non-empty string")


def validate_record(record: Any, *, allow_unknown_sha: bool) -> None:
    if not isinstance(record, dict):
        raise LedgerError("record must be a JSON object")
    actual = set(record)
    expected = set(RECORD_FIELDS)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise LedgerError(f"record fields mismatch: missing={missing}, extra={extra}")
    reject_secrets(record)
    for field in RECORD_FIELDS:
        value = record[field]
        if field in LIST_FIELDS:
            if not isinstance(value, list) or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                raise LedgerError(f"{field} must be an array of non-empty strings")
        elif field in COUNT_FIELDS:
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise LedgerError(f"{field} must be a non-negative integer or null")
        elif field in TRISTATE_FIELDS:
            if value not in {"YES", "NO", "UNKNOWN"}:
                raise LedgerError(f"{field} must be YES, NO, or UNKNOWN")
        else:
            _nonempty_string(value, field)
    sha = record["CURRENT_SHA"]
    if not SHA_RE.fullmatch(sha) and not (allow_unknown_sha and sha == "UNKNOWN"):
        raise LedgerError("CURRENT_SHA must be a full lowercase 40-character Git SHA")
    for evidence in record["LAST_EVIDENCE"]:
        if not evidence.startswith("https://"):
            raise LedgerError("LAST_EVIDENCE entries must be durable https:// URLs")


def _entry_hash(entry: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in entry.items() if key != "entry_sha256"}
    return digest(unsigned)


def validate_bundle(bundle: Any) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        raise LedgerError("ledger root must be a JSON object")
    required = {
        "format",
        "schema_version",
        "revision",
        "non_authority",
        "record",
        "history",
    }
    if set(bundle) != required:
        raise LedgerError("ledger root fields do not match the canonical format")
    if bundle["format"] != FORMAT or bundle["schema_version"] != SCHEMA_VERSION:
        raise LedgerError("unsupported ledger format or schema version")
    if bundle["non_authority"] != NON_AUTHORITY:
        raise LedgerError("non-authority declaration is missing or changed")
    revision = bundle["revision"]
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise LedgerError("revision must be a non-negative integer")
    validate_record(bundle["record"], allow_unknown_sha=revision == 0)
    history = bundle["history"]
    if not isinstance(history, list) or len(history) != revision + 1:
        raise LedgerError("history must contain exactly one entry per revision")
    previous_hash = None
    previous_record = None
    for index, entry in enumerate(history):
        if not isinstance(entry, dict):
            raise LedgerError(f"history entry {index} must be an object")
        expected_fields = {
            "revision",
            "timestamp_utc",
            "updated_by",
            "operation",
            "changed_fields",
            "record",
            "record_sha256",
            "previous_entry_sha256",
            "entry_sha256",
        }
        if set(entry) != expected_fields:
            raise LedgerError(f"history entry {index} fields are invalid")
        if entry["revision"] != index:
            raise LedgerError(f"history entry {index} revision is invalid")
        if entry["operation"] not in {"INIT", "UPDATE"}:
            raise LedgerError(f"history entry {index} operation is invalid")
        if index == 0 and entry["operation"] != "INIT":
            raise LedgerError("first history entry must be INIT")
        if index > 0 and entry["operation"] != "UPDATE":
            raise LedgerError(f"history entry {index} must be UPDATE")
        if not isinstance(entry["changed_fields"], list) or entry["changed_fields"] != sorted(
            entry["changed_fields"]
        ):
            raise LedgerError(f"history entry {index} changed_fields are invalid")
        if not entry["changed_fields"] or not set(entry["changed_fields"]).issubset(
            RECORD_FIELDS
        ):
            raise LedgerError(f"history entry {index} changed_fields are invalid")
        _nonempty_string(entry["timestamp_utc"], f"history[{index}].timestamp_utc")
        _nonempty_string(entry["updated_by"], f"history[{index}].updated_by")
        validate_record(entry["record"], allow_unknown_sha=index == 0)
        expected_changed = (
            sorted(RECORD_FIELDS)
            if previous_record is None
            else sorted(
                field
                for field in RECORD_FIELDS
                if previous_record[field] != entry["record"][field]
            )
        )
        if entry["changed_fields"] != expected_changed:
            raise LedgerError(f"history entry {index} changed_fields do not match record")
        if entry["updated_by"] != entry["record"]["LAST_UPDATED_BY"]:
            raise LedgerError(f"history entry {index} updated_by does not match record")
        if entry["record_sha256"] != digest(entry["record"]):
            raise LedgerError(f"history entry {index} record hash is invalid")
        if entry["previous_entry_sha256"] != previous_hash:
            raise LedgerError(f"history entry {index} chain is invalid")
        if entry["entry_sha256"] != _entry_hash(entry):
            raise LedgerError(f"history entry {index} hash is invalid")
        previous_hash = entry["entry_sha256"]
        previous_record = entry["record"]
    if history[-1]["record"] != bundle["record"]:
        raise LedgerError("current record does not match the latest history entry")
    return bundle


def load_bundle(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise LedgerError(f"refusing symlink ledger path: {path}")
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise LedgerError(f"ledger does not exist: {path}") from exc
    except OSError as exc:
        raise LedgerError(f"cannot read ledger {path}: {exc}") from exc
    try:
        return validate_bundle(json.loads(raw))
    except json.JSONDecodeError as exc:
        raise LedgerError(f"ledger is corrupt JSON: {exc}") from exc


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(directory, flags)
    except OSError:
        return
    try:
        try:
            os.fsync(descriptor)
        except OSError as exc:
            if exc.errno not in {errno.EBADF, errno.EINVAL, getattr(errno, "ENOTSUP", 0)}:
                raise
    finally:
        os.close(descriptor)


def atomic_write(path: Path, bundle: dict[str, Any]) -> None:
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise LedgerError(f"refusing symlink ledger path: {path}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(bundle, stream, ensure_ascii=True, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(parent)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()


@contextlib.contextmanager
def writer_lock(path: Path, timeout: float) -> Iterator[None]:
    if timeout < 0 or timeout > 60:
        raise LedgerError("lock timeout must be between 0 and 60 seconds")
    lock_path = path.with_name(f"{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.is_symlink():
        raise LedgerError(f"refusing symlink lock path: {lock_path}")
    with lock_path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                _lock_stream(stream)
                break
            except (BlockingIOError, OSError) as exc:
                if isinstance(exc, OSError) and exc.errno not in {
                    errno.EACCES,
                    errno.EAGAIN,
                }:
                    raise LedgerError(f"cannot acquire writer lock: {exc}") from exc
                if time.monotonic() >= deadline:
                    raise LedgerError(
                        f"writer lock busy after {timeout:.2f}s: {lock_path}"
                    ) from exc
                time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
        try:
            yield
        finally:
            _unlock_stream(stream)


def _lock_stream(stream: Any) -> None:
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_stream(stream: Any) -> None:
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _history_entry(
    revision: int,
    record: dict[str, Any],
    updated_by: str,
    operation: str,
    changed_fields: list[str],
    previous_hash: str | None,
) -> dict[str, Any]:
    entry = {
        "revision": revision,
        "timestamp_utc": utc_now(),
        "updated_by": updated_by,
        "operation": operation,
        "changed_fields": sorted(changed_fields),
        "record": copy.deepcopy(record),
        "record_sha256": digest(record),
        "previous_entry_sha256": previous_hash,
    }
    entry["entry_sha256"] = _entry_hash(entry)
    return entry


def initialize(path: Path, record: dict[str, Any], timeout: float) -> dict[str, Any]:
    validate_record(record, allow_unknown_sha=True)
    with writer_lock(path, timeout):
        if path.exists():
            raise LedgerError(f"ledger already exists: {path}")
        bundle = {
            "format": FORMAT,
            "schema_version": SCHEMA_VERSION,
            "revision": 0,
            "non_authority": NON_AUTHORITY,
            "record": copy.deepcopy(record),
            "history": [
                _history_entry(
                    0,
                    record,
                    record["LAST_UPDATED_BY"],
                    "INIT",
                    list(RECORD_FIELDS),
                    None,
                )
            ],
        }
        validate_bundle(bundle)
        atomic_write(path, bundle)
    return bundle


def update(
    path: Path,
    expected_revision: int,
    updates: dict[str, Any],
    updated_by: str,
    timeout: float,
) -> dict[str, Any]:
    _nonempty_string(updated_by, "updated_by")
    if not updates:
        raise LedgerError("at least one --set update is required")
    invalid = sorted(set(updates) - set(RECORD_FIELDS))
    if invalid:
        raise LedgerError(f"unknown record fields: {invalid}")
    if "LAST_UPDATED_BY" in updates:
        raise LedgerError("use --updated-by instead of setting LAST_UPDATED_BY")
    reject_secrets(updates, "updates")
    with writer_lock(path, timeout):
        bundle = load_bundle(path)
        if bundle["revision"] != expected_revision:
            raise LedgerError(
                f"revision conflict: expected {expected_revision}, "
                f"current {bundle['revision']}"
            )
        record = copy.deepcopy(bundle["record"])
        changed = []
        for field, value in updates.items():
            if record[field] != value:
                record[field] = value
                changed.append(field)
        if not changed:
            raise LedgerError("update makes no meaningful change")
        if record["LAST_UPDATED_BY"] != updated_by:
            record["LAST_UPDATED_BY"] = updated_by
            changed.append("LAST_UPDATED_BY")
        validate_record(record, allow_unknown_sha=False)
        revision = bundle["revision"] + 1
        entry = _history_entry(
            revision,
            record,
            updated_by,
            "UPDATE",
            changed,
            bundle["history"][-1]["entry_sha256"],
        )
        updated = {
            **bundle,
            "revision": revision,
            "record": record,
            "history": [*bundle["history"], entry],
        }
        validate_bundle(updated)
        atomic_write(path, updated)
    return updated


def parse_assignment(value: str) -> tuple[str, Any]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--set requires FIELD=VALUE")
    field, raw = value.split("=", 1)
    if not field:
        raise argparse.ArgumentTypeError("--set field cannot be empty")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = raw
    return field, parsed


def render(bundle: dict[str, Any]) -> str:
    lines = [
        "COURIER AGENT HANDOFF LEDGER",
        f"FORMAT: {bundle['format']}",
        f"SCHEMA_VERSION: {bundle['schema_version']}",
        f"REVISION: {bundle['revision']}",
        f"NON_AUTHORITY: {bundle['non_authority']}",
    ]
    record = bundle["record"]
    for field in RECORD_FIELDS:
        value = record[field]
        if isinstance(value, list):
            rendered = "NONE" if not value else " | ".join(value)
        elif value is None:
            rendered = "UNKNOWN"
        else:
            rendered = str(value)
        lines.append(f"{field}: {rendered}")
    return "\n".join(lines) + "\n"


def next_action(bundle: dict[str, Any]) -> dict[str, Any]:
    record = bundle["record"]
    return {
        "BRANCH": record["BRANCH"],
        "CURRENT_SHA": record["CURRENT_SHA"],
        "FIRST_CAUSAL_BLOCKER": record["FIRST_CAUSAL_BLOCKER"],
        "BLOCKER_OWNER": record["BLOCKER_OWNER"],
        "NEXT_EXECUTABLE_ACTION": record["NEXT_EXECUTABLE_ACTION"],
        "RUNTIME_IDENTITY": record["RUNTIME_IDENTITY"],
        "STATUS": record["STATUS"],
        "CONTINUATION_CHECKPOINT": record["CONTINUATION_CHECKPOINT"],
        "REVISION": bundle["revision"],
        "NON_AUTHORITY": bundle["non_authority"],
    }


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True))


def _read_record(path: str) -> dict[str, Any]:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LedgerError(f"record input is invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise LedgerError("record input must be a JSON object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create a new ledger")
    init_parser.add_argument("ledger", type=Path)
    init_parser.add_argument("--record", required=True, help="record JSON file, or -")
    init_parser.add_argument("--lock-timeout", type=float, default=5.0)

    for command in ("read", "render", "history", "next-action"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("ledger", type=Path)

    update_parser = subparsers.add_parser("update", help="update selected fields")
    update_parser.add_argument("ledger", type=Path)
    update_parser.add_argument("--expected-revision", required=True, type=int)
    update_parser.add_argument("--updated-by", required=True)
    update_parser.add_argument(
        "--set", dest="assignments", action="append", required=True, type=parse_assignment
    )
    update_parser.add_argument("--lock-timeout", type=float, default=5.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            bundle = initialize(
                args.ledger, _read_record(args.record), args.lock_timeout
            )
            print_json(bundle)
        elif args.command == "update":
            updates: dict[str, Any] = {}
            for field, value in args.assignments:
                if field in updates:
                    raise LedgerError(f"duplicate --set field: {field}")
                updates[field] = value
            bundle = update(
                args.ledger,
                args.expected_revision,
                updates,
                args.updated_by,
                args.lock_timeout,
            )
            print_json(bundle)
        else:
            bundle = load_bundle(args.ledger)
            if args.command == "read":
                print_json(bundle)
            elif args.command == "render":
                print(render(bundle), end="")
            elif args.command == "history":
                print_json(bundle["history"])
            elif args.command == "next-action":
                print_json(next_action(bundle))
    except (LedgerError, OSError) as exc:
        print(f"agent-handoff-ledger: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
