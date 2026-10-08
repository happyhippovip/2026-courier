"""Canonical ledger-backed work queue.

Seed files in ``registries/work_items`` are the catalog. Claim, renew, and
release events append to a JSONL ledger and are the only runtime state.
Seed files are not rewritten. The module does not talk to the controller
and does not read ``courier_worker``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatchcase
from pathlib import Path

STATUSES = ("READY", "CLAIMED", "DONE", "BLOCKED")
MAX_ITEM_BYTES = 64 * 1024
MAX_LEDGER_BYTES = 1024 * 1024
MAX_TTL_SECONDS = 7 * 24 * 3600
_TOKEN = re.compile(r"^[A-Za-z0-9._:-]+$")
_TIME = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ITEMS = REPO_ROOT / "registries" / "work_items"
DEFAULT_SCHEMA = Path(__file__).resolve().parent / "schemas" / "work_item.schema.json"
DEFAULT_LEDGER = REPO_ROOT / "registries" / "work_queue_ledger.jsonl"


class WorkQueueError(Exception):
    """A refused or unreadable queue operation. ``code`` is a short token."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def list_ready(queue: "WorkQueue", open_pr_files=None, done_prs=None, now=None) -> list[dict]:
    return queue.list_ready(open_pr_files=open_pr_files, done_prs=done_prs, now=now)


def claim(queue: "WorkQueue", item, holder, ttl, host="local", now=None, done_prs=None, open_pr_files=None) -> dict:
    return queue.claim(item, holder, ttl, host=host, now=now, done_prs=done_prs, open_pr_files=open_pr_files)


def renew(queue: "WorkQueue", item, holder, ttl, now=None) -> dict:
    return queue.renew(item, holder, ttl, now=now)


def release(queue: "WorkQueue", item, holder, result, now=None) -> dict:
    return queue.release(item, holder, result, now=now)


class WorkQueue:
    def __init__(self, items_dir=None, ledger_path=None, schema_path=None):
        self.items_dir = Path(items_dir) if items_dir is not None else DEFAULT_ITEMS
        self.ledger_path = Path(ledger_path) if ledger_path is not None else DEFAULT_LEDGER
        self.schema_path = Path(schema_path) if schema_path is not None else DEFAULT_SCHEMA

    def list_ready(self, open_pr_files=None, done_prs=None, now=None) -> list[dict]:
        moment = _now(now)
        with self._lock():
            items = self._effective(moment)
        occupied = [item for item in items.values() if _held(item, moment)]
        pr_files = [_norm(path) for path in (open_pr_files or [])]
        done = {_norm_token(value) for value in (done_prs or [])}
        ready = []
        for item in items.values():
            if not _claimable_status(item, moment):
                continue
            if not _deps_met(item, items, done):
                continue
            if _blocked_by_scope(item, occupied, pr_files):
                continue
            ready.append(_public(item))
        ready.sort(key=lambda item: item["id"])
        return ready

    def claim(self, item, holder, ttl, host="local", now=None, done_prs=None, open_pr_files=None) -> dict:
        item_id = _require_token(item, "ITEM")
        holder = _require_token(holder, "HOLDER")
        host = _require_token(host, "HOST")
        ttl = _require_ttl(ttl)
        moment = _now(now)
        done = {_norm_token(value) for value in (done_prs or [])}
        pr_files = [_norm(path) for path in (open_pr_files or [])]
        with self._lock():
            items = self._effective(moment)
            current = items.get(item_id)
            if current is None:
                raise WorkQueueError("UNKNOWN_ITEM")
            if _held(current, moment):
                if current["lease"]["holder"] == holder:
                    return _claim_view(current, idempotent=True)
                raise WorkQueueError("DUPLICATE_CLAIM")
            if not _claimable_status(current, moment) or not _deps_met(current, items, done):
                raise WorkQueueError("NOT_CLAIMABLE")
            occupied = [row for row in items.values() if _held(row, moment)]
            if _blocked_by_scope(current, occupied, pr_files):
                raise WorkQueueError("SCOPE_OVERLAP")
            expires = _stamp(moment + timedelta(seconds=ttl))
            self._append({
                "type": "CLAIM",
                "item_id": item_id,
                "holder": holder,
                "host": host,
                "expires_at": expires,
                "at": _stamp(moment),
            })
            current["status"] = "CLAIMED"
            current["lease"] = {"holder": holder, "host": host, "expires_at": expires}
            return _claim_view(current, idempotent=False)

    def renew(self, item, holder, ttl, now=None) -> dict:
        item_id = _require_token(item, "ITEM")
        holder = _require_token(holder, "HOLDER")
        ttl = _require_ttl(ttl)
        moment = _now(now)
        with self._lock():
            items = self._effective(moment)
            current = items.get(item_id)
            if current is None:
                raise WorkQueueError("UNKNOWN_ITEM")
            if not _held(current, moment) or current["lease"]["holder"] != holder:
                raise WorkQueueError("NOT_HOLDER")
            expires = _stamp(moment + timedelta(seconds=ttl))
            self._append({
                "type": "RENEW",
                "item_id": item_id,
                "holder": holder,
                "host": current["lease"]["host"],
                "expires_at": expires,
                "at": _stamp(moment),
            })
            current["lease"]["expires_at"] = expires
            return _claim_view(current, idempotent=False)

    def release(self, item, holder, result, now=None) -> dict:
        item_id = _require_token(item, "ITEM")
        holder = _require_token(holder, "HOLDER")
        result = _require_result(result)
        moment = _now(now)
        with self._lock():
            items = self._effective(moment)
            current = items.get(item_id)
            if current is None:
                raise WorkQueueError("UNKNOWN_ITEM")
            if current["status"] == "DONE" and current.get("result") == result and current.get("released_by") == holder:
                return {"item_id": item_id, "status": "DONE", "result": result, "idempotent": True}
            if current["status"] == "DONE":
                raise WorkQueueError("ALREADY_DONE")
            if not _held(current, moment) or current["lease"]["holder"] != holder:
                raise WorkQueueError("NOT_HOLDER")
            self._append({
                "type": "RELEASE",
                "item_id": item_id,
                "holder": holder,
                "result": result,
                "at": _stamp(moment),
            })
            return {"item_id": item_id, "status": "DONE", "result": result, "idempotent": False}

    def items(self, now=None) -> list[dict]:
        moment = _now(now)
        with self._lock():
            rows = self._effective(moment)
        return [_public(row) for row in sorted(rows.values(), key=lambda item: item["id"])]

    def _effective(self, moment: datetime) -> dict[str, dict]:
        seeds = _load_seeds(self.items_dir, self.schema_path)
        events = _read_ledger(self.ledger_path)
        for event in events:
            _apply(seeds, event)
        for item in seeds.values():
            if item["status"] == "CLAIMED" and not _held(item, moment):
                item["status"] = "READY"
                item["lease"] = None
        return seeds

    def _append(self, event: dict) -> None:
        line = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        path = self.ledger_path
        if path.is_symlink():
            raise WorkQueueError("UNREADABLE")
        existing = path.stat().st_size if path.exists() else 0
        if existing + len(line) > MAX_LEDGER_BYTES:
            raise WorkQueueError("LEDGER_TOO_LARGE")
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        try:
            os.write(fd, line)
            os.fsync(fd)
        finally:
            os.close(fd)

    @contextmanager
    def _lock(self):
        lock_path = self.ledger_path.with_suffix(self.ledger_path.suffix + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"\0")
            os.lseek(fd, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def render_prompt(item: dict, holder: str) -> str:
    scope = "\n".join(f"- {path}" for path in item["files_scope"])
    acceptance = "\n".join(f"- {line}" for line in item["acceptance"])
    hints = ", ".join(item["provider_hints"]) or "none"
    deps = ", ".join(item["depends_on"]) or "none"
    return (
        f"id: {item['id']}\n"
        f"title: {item['title']}\n"
        f"lane: {item['lane']}\n"
        f"branch: {item['branch']}\n"
        f"holder: {holder}\n"
        f"depends_on: {deps}\n"
        f"provider_hints: {hints}\n"
        f"files_scope:\n{scope}\n"
        f"acceptance:\n{acceptance}\n"
        "---\n"
        f"Work item {item['id']} only. Branch {item['branch']}.\n"
        "Write only paths that match files_scope. Do not edit other files.\n"
        "Acceptance is the list above. Claim the item before writing, then release it with the result.\n"
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m courier_core.work_queue")
    parser.add_argument("--items", default=str(DEFAULT_ITEMS))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    sub = parser.add_subparsers(dest="command", required=True)

    nxt = sub.add_parser("next")
    nxt.add_argument("--holder", required=True)
    nxt.add_argument("--open-pr-file", action="append", default=[])
    nxt.add_argument("--done-pr", action="append", default=[])

    clm = sub.add_parser("claim")
    clm.add_argument("--item", required=True)
    clm.add_argument("--holder", required=True)
    clm.add_argument("--ttl", type=int, required=True)
    clm.add_argument("--host", default="local")
    clm.add_argument("--open-pr-file", action="append", default=[])
    clm.add_argument("--done-pr", action="append", default=[])

    ren = sub.add_parser("renew")
    ren.add_argument("--item", required=True)
    ren.add_argument("--holder", required=True)
    ren.add_argument("--ttl", type=int, required=True)

    rel = sub.add_parser("release")
    rel.add_argument("--item", required=True)
    rel.add_argument("--holder", required=True)
    rel.add_argument("--result", required=True)

    args = parser.parse_args(argv)
    queue = WorkQueue(args.items, args.ledger, args.schema)
    try:
        if args.command == "next":
            ready = queue.list_ready(open_pr_files=args.open_pr_file, done_prs=args.done_pr)
            if not ready:
                print("NO_READY_ITEM")
                return 0
            print(render_prompt(ready[0], args.holder), end="")
            return 0
        if args.command == "claim":
            claimed = queue.claim(
                args.item, args.holder, args.ttl, host=args.host,
                done_prs=args.done_pr, open_pr_files=args.open_pr_file,
            )
        elif args.command == "renew":
            claimed = queue.renew(args.item, args.holder, args.ttl)
        else:
            claimed = queue.release(args.item, args.holder, args.result)
    except WorkQueueError as exc:
        print(exc.code, file=sys.stderr)
        return 2
    print(json.dumps(claimed, sort_keys=True))
    return 0


def _load_seeds(items_dir: Path, schema_path: Path) -> dict[str, dict]:
    schema = _read_json(schema_path, MAX_ITEM_BYTES)
    if not items_dir.is_dir() or items_dir.is_symlink():
        raise WorkQueueError("UNREADABLE")
    found = {}
    for path in sorted(items_dir.glob("*.json")):
        if path.is_symlink() or not path.is_file():
            raise WorkQueueError("UNREADABLE")
        document = _read_json(path, MAX_ITEM_BYTES)
        _validate(document, schema)
        if document["id"] != path.stem:
            raise WorkQueueError("ID_MISMATCH")
        if document["status"] == "CLAIMED":
            if not isinstance(document["lease"], dict):
                raise WorkQueueError("LEASE_REQUIRED")
        elif document["lease"] is not None:
            raise WorkQueueError("LEASE_UNEXPECTED")
        if document["id"] in found:
            raise WorkQueueError("DUPLICATE_ID")
        found[document["id"]] = document
        found[document["id"]]["result"] = None
        found[document["id"]]["released_by"] = None
    if not found:
        raise WorkQueueError("UNREADABLE")
    return found


def _validate(document, schema) -> None:
    if not isinstance(document, dict):
        raise WorkQueueError("INVALID_ITEM")
    if schema.get("additionalProperties") is False and set(document) - set(schema.get("properties", {})):
        raise WorkQueueError("INVALID_ITEM")
    required = schema.get("required", [])
    if any(name not in document for name in required):
        raise WorkQueueError("INVALID_ITEM")
    for name, rules in schema.get("properties", {}).items():
        if name not in document:
            continue
        if not _matches(document[name], rules):
            raise WorkQueueError("INVALID_ITEM")
    if len(document["files_scope"]) != len(set(document["files_scope"])):
        raise WorkQueueError("INVALID_ITEM")
    if any(".." in scope or scope.startswith("/") for scope in document["files_scope"]):
        raise WorkQueueError("INVALID_ITEM")
    if len(document["depends_on"]) != len(set(document["depends_on"])):
        raise WorkQueueError("INVALID_ITEM")


def _matches(value, rules) -> bool:
    if "anyOf" in rules:
        return any(_matches(value, option) for option in rules["anyOf"])
    expected = rules.get("type")
    if isinstance(expected, list):
        return any(_matches(value, {**rules, "type": one}) for one in expected)
    if expected == "null":
        return value is None
    if expected == "string":
        if not isinstance(value, str):
            return False
        if "minLength" in rules and len(value) < rules["minLength"]:
            return False
        if "maxLength" in rules and len(value) > rules["maxLength"]:
            return False
        if "pattern" in rules and re.fullmatch(rules["pattern"], value) is None:
            return False
        if "enum" in rules and value not in rules["enum"]:
            return False
        return True
    if expected == "array":
        if not isinstance(value, list):
            return False
        if "minItems" in rules and len(value) < rules["minItems"]:
            return False
        if "maxItems" in rules and len(value) > rules["maxItems"]:
            return False
        item_rules = rules.get("items")
        return item_rules is None or all(_matches(item, item_rules) for item in value)
    if expected == "object":
        if not isinstance(value, dict):
            return False
        if rules.get("additionalProperties") is False and set(value) - set(rules.get("properties", {})):
            return False
        if any(name not in value for name in rules.get("required", [])):
            return False
        return all(name not in value or _matches(value[name], child) for name, child in rules.get("properties", {}).items())
    return False


def _read_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    if path.is_symlink() or not path.is_file():
        raise WorkQueueError("UNREADABLE")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise WorkQueueError("UNREADABLE") from exc
    if size > MAX_LEDGER_BYTES:
        raise WorkQueueError("LEDGER_TOO_LARGE")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise WorkQueueError("UNREADABLE") from exc
    if len(raw) > MAX_LEDGER_BYTES:
        raise WorkQueueError("LEDGER_TOO_LARGE")
    events = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise WorkQueueError("UNREADABLE") from exc
        if not isinstance(event, dict) or event.get("type") not in ("CLAIM", "RENEW", "RELEASE"):
            raise WorkQueueError("UNREADABLE")
        events.append(event)
    return events


def _apply(items: dict[str, dict], event: dict) -> None:
    item = items.get(event.get("item_id"))
    if item is None or item["status"] in ("DONE", "BLOCKED"):
        return
    kind = event["type"]
    if kind == "CLAIM":
        if not _event_token(event.get("holder")) or not _event_token(event.get("host")):
            raise WorkQueueError("UNREADABLE")
        if _TIME.fullmatch(str(event.get("expires_at") or "")) is None:
            raise WorkQueueError("UNREADABLE")
        item["status"] = "CLAIMED"
        item["lease"] = {"holder": event["holder"], "host": event["host"], "expires_at": event["expires_at"]}
        return
    if kind == "RENEW":
        if item["status"] != "CLAIMED" or not isinstance(item.get("lease"), dict):
            return
        if item["lease"]["holder"] != event.get("holder"):
            return
        if _TIME.fullmatch(str(event.get("expires_at") or "")) is None:
            raise WorkQueueError("UNREADABLE")
        item["lease"]["expires_at"] = event["expires_at"]
        return
    if item["status"] != "CLAIMED" or not isinstance(item.get("lease"), dict):
        return
    result = event.get("result")
    if not isinstance(result, str) or not result.strip() or len(result) > 200 or any(ch in result for ch in "\n\r"):
        raise WorkQueueError("UNREADABLE")
    if not _event_token(event.get("holder")) or item["lease"]["holder"] != event["holder"]:
        return
    item["status"] = "DONE"
    item["lease"] = None
    item["result"] = result.strip()
    item["released_by"] = event["holder"]


def _read_json(path: Path, cap: int):
    if path.is_symlink() or not path.is_file():
        raise WorkQueueError("UNREADABLE")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise WorkQueueError("UNREADABLE") from exc
    if len(raw) > cap:
        raise WorkQueueError("UNREADABLE")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise WorkQueueError("UNREADABLE") from exc


def _held(item: dict, moment: datetime) -> bool:
    if item["status"] != "CLAIMED" or not isinstance(item.get("lease"), dict):
        return False
    expires = _parse_time(item["lease"].get("expires_at"))
    return expires is not None and expires > moment


def _claimable_status(item: dict, moment: datetime) -> bool:
    if item["status"] == "READY":
        return True
    return item["status"] == "CLAIMED" and not _held(item, moment)


def _deps_met(item: dict, items: dict[str, dict], done_prs: set[str]) -> bool:
    for dep in item["depends_on"]:
        if dep in items:
            if items[dep]["status"] != "DONE":
                return False
            continue
        if dep in done_prs:
            continue
        return False
    return True


def _blocked_by_scope(item: dict, occupied: list[dict], pr_files: list[str]) -> bool:
    for other in occupied:
        if other["id"] == item["id"]:
            continue
        if scopes_overlap(item["files_scope"], other["files_scope"]):
            return True
    for path in pr_files:
        if any(_paths_overlap(scope, path) for scope in item["files_scope"]):
            return True
    return False


def scopes_overlap(left, right) -> bool:
    return any(_paths_overlap(a, b) for a in left for b in right)


def _paths_overlap(left: str, right: str) -> bool:
    a, b = _norm(left), _norm(right)
    if a == b or fnmatchcase(a, b) or fnmatchcase(b, a):
        return True
    a_wild, b_wild = _wild(a), _wild(b)
    if a_wild and not b_wild:
        return b.startswith(_prefix(a) + "/")
    if b_wild and not a_wild:
        return a.startswith(_prefix(b) + "/")
    if a_wild and b_wild:
        pa, pb = _prefix(a), _prefix(b)
        if not pa or not pb:
            return True
        return pa == pb or pa.startswith(pb + "/") or pb.startswith(pa + "/")
    return False


def _prefix(pattern: str) -> str:
    parts = []
    for part in pattern.split("/"):
        if _wild(part):
            break
        parts.append(part)
    return "/".join(parts)


def _wild(value: str) -> bool:
    return any(ch in value for ch in "*?[")


def _public(item: dict) -> dict:
    return {
        "id": item["id"],
        "title": item["title"],
        "lane": item["lane"],
        "branch": item["branch"],
        "files_scope": list(item["files_scope"]),
        "depends_on": list(item["depends_on"]),
        "acceptance": list(item["acceptance"]),
        "provider_hints": list(item["provider_hints"]),
        "status": "READY" if item["status"] == "READY" else item["status"],
        "lease": None if item["lease"] is None else dict(item["lease"]),
    }


def _claim_view(item: dict, idempotent: bool) -> dict:
    lease = item["lease"]
    return {
        "item_id": item["id"],
        "status": "CLAIMED",
        "holder": lease["holder"],
        "host": lease["host"],
        "expires_at": lease["expires_at"],
        "idempotent": idempotent,
    }


def _require_token(value, code: str) -> str:
    if not isinstance(value, str) or _TOKEN.fullmatch(value) is None or len(value) > 64:
        raise WorkQueueError(code)
    return value


def _require_ttl(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_TTL_SECONDS:
        raise WorkQueueError("TTL")
    return value


def _require_result(value) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 200 or any(ch in value for ch in "\n\r"):
        raise WorkQueueError("RESULT")
    return value.strip()


def _event_token(value) -> bool:
    return isinstance(value, str) and _TOKEN.fullmatch(value) is not None and len(value) <= 64


def _now(value) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise WorkQueueError("CLOCK")
        return value.astimezone(timezone.utc)
    raise WorkQueueError("CLOCK")


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_time(value):
    if not isinstance(value, str) or _TIME.fullmatch(value) is None:
        return None
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None


def _norm(value: str) -> str:
    return str(value).replace("\\", "/").lstrip("./")


def _norm_token(value) -> str:
    return str(value)


if __name__ == "__main__":
    sys.exit(main())
