"""Canonical ledger-backed work queue.

Seed files in ``registries/work_items`` are the catalog. Claim, renew, and
release events append to a JSONL ledger and are the only runtime state.
Seed files are not rewritten. The module does not talk to the controller
and does not read ``courier_worker``.
"""

from __future__ import annotations

import argparse
import errno
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
_HOLDER = re.compile(r"^[A-Za-z0-9._:/-]+$")
_MODULE = re.compile(r"^[A-Za-z0-9._-]+$")
EVENT_TYPES = ("CLAIM", "RENEW", "RELEASE", "SPAWN", "ATTACH", "RECLAIM", "RECONCILE", "PARK")
RECONCILABLE = ("COMPLETE_VERIFIED", "FAILED", "CANCELLED")
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


def reclaim(queue: "WorkQueue", item, actor, reason, now=None) -> dict:
    return queue.reclaim(item, actor, reason, now=now)


def spawn(queue: "WorkQueue", template, module, now=None) -> dict:
    return queue.spawn(template, module, now=now)


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

    def claim(self, item, holder, ttl, host="local", now=None, done_prs=None, open_pr_files=None,
              announce=False) -> dict:
        """``announce=True`` promises an ATTACH before the mission is handed off, so an expired
        lease without ATTACH proves nothing was handed off and another holder may take it over."""
        item_id = _require_token(item, "ITEM")
        holder = _require_holder(holder)
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
            if current.get("template") or _sticky(current) or (current.get("claim_once") and current["status"] == "CLAIMED"):
                raise WorkQueueError("NOT_CLAIMABLE")
            if not _claimable_status(current, moment) or not _deps_met(current, items, done):
                raise WorkQueueError("NOT_CLAIMABLE")
            if (current.get("attached") or {}).get("holder") not in (None, holder):
                # Handed off by another holder whose lease expired: its mission may still run.
                raise WorkQueueError("ATTACHED_ELSEWHERE")
            occupied = [row for row in items.values() if _held(row, moment)]
            if _blocked_by_scope(current, occupied, pr_files):
                raise WorkQueueError("SCOPE_OVERLAP")
            expires = _stamp(moment + timedelta(seconds=ttl))
            event = {
                "type": "CLAIM",
                "item_id": item_id,
                "holder": holder,
                "host": host,
                "expires_at": expires,
                "at": _stamp(moment),
            }
            if announce:
                event["announce"] = True
            self._append(event)
            current["status"] = "CLAIMED"
            current["lease"] = {"holder": holder, "host": host, "expires_at": expires}
            if announce:
                current["lease"]["announce"] = True
            return _claim_view(current, idempotent=False)

    def renew(self, item, holder, ttl, now=None) -> dict:
        item_id = _require_token(item, "ITEM")
        holder = _require_holder(holder)
        ttl = _require_ttl(ttl)
        moment = _now(now)
        with self._lock():
            items = self._effective(moment)
            current = items.get(item_id)
            if current is None:
                raise WorkQueueError("UNKNOWN_ITEM")
            if _sticky(current):
                raise WorkQueueError("NOT_RENEWABLE")
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
        holder = _require_holder(holder)
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

    def attach(self, item, holder, ref, now=None) -> dict:
        """Record that the holder is handing the mission off (before it does so)."""
        item_id = _require_token(item, "ITEM")
        holder = _require_holder(holder)
        ref = _require_holder(ref)
        moment = _now(now)
        with self._lock():
            current = self._effective(moment).get(item_id)
            if current is None:
                raise WorkQueueError("UNKNOWN_ITEM")
            if not _held(current, moment) or current["lease"]["holder"] != holder:
                raise WorkQueueError("NOT_HOLDER")
            if _sticky(current):
                # A sticky lease never expires, so nobody can take it over: nothing to announce
                # (and replay ignores events on sticky items, so an ATTACH would repeat forever).
                return {"item_id": item_id, "attached": holder, "idempotent": True}
            if current.get("attached") == {"holder": holder, "ref": ref}:
                return {"item_id": item_id, "attached": holder, "idempotent": True}
            self._append({"type": "ATTACH", "item_id": item_id, "holder": holder, "ref": ref,
                          "at": _stamp(moment)})
            return {"item_id": item_id, "attached": holder, "idempotent": False}

    def reclaim(self, item, actor, reason, now=None) -> dict:
        """A human frees a workkey whose lease expired. Needs a named actor and a reason."""
        item_id = _require_token(item, "ITEM")
        actor = _require_holder(actor)
        reason = _require_text(reason, "REASON")
        moment = _now(now)
        with self._lock():
            current = self._effective(moment).get(item_id)
            if current is None:
                raise WorkQueueError("UNKNOWN_ITEM")
            if _held(current, moment):
                raise WorkQueueError("LEASE_LIVE")
            ends = None
            if current["status"] == "READY":
                ends = current.get("expired_lease")
            elif current["status"] == "CLAIMED" and current.get("claim_once") and not _sticky(current):
                ends = current["lease"]                          # a one-time child keeps its dead lease
            elif current["status"] == "BLOCKED" and current.get("parked"):
                ends = {"holder": current["parked"]["holder"], "expires_at": "parked:" + current["parked"]["at"]}
            expired_holder = (ends or {}).get("holder")
            if not expired_holder:
                raise WorkQueueError("NOT_RECLAIMABLE")
            self._append({"type": "RECLAIM", "item_id": item_id, "actor": actor, "reason": reason,
                          "expired_holder": expired_holder, "ends": ends["expires_at"], "at": _stamp(moment)})
            return {"item_id": item_id, "status": "READY", "reclaimed_from": expired_holder, "actor": actor}

    def park(self, item, holder, reason, now=None) -> dict:
        """The holder's mission ended without a verified FINAL (ERROR, BLOCKED): the workkey
        becomes BLOCKED for a human (``reclaim``) and the holder is free for other work."""
        item_id = _require_token(item, "ITEM")
        holder = _require_holder(holder)
        reason = _require_text(reason, "REASON")
        moment = _now(now)
        with self._lock():
            current = self._effective(moment).get(item_id)
            if current is None:
                raise WorkQueueError("UNKNOWN_ITEM")
            if not _held(current, moment) or current["lease"]["holder"] != holder:
                raise WorkQueueError("NOT_HOLDER")
            self._append({"type": "PARK", "item_id": item_id, "holder": holder, "reason": reason,
                          "at": _stamp(moment)})
            return {"item_id": item_id, "status": "BLOCKED", "reason": reason}

    def reconcile(self, item, observed, evidence, actor, now=None) -> dict:
        """Settle an expired, attached workkey from the controller state of its task.

        COMPLETE_VERIFIED marks it DONE (no new task); FAILED or CANCELLED frees it. Anything
        else (BLOCKED, RUNNING, unknown) is refused: a human decides or the holder returns.
        """
        item_id = _require_token(item, "ITEM")
        if observed not in RECONCILABLE:
            raise WorkQueueError("NOT_RECONCILABLE")
        evidence = _require_text(evidence, "EVIDENCE")
        actor = _require_holder(actor)
        moment = _now(now)
        with self._lock():
            current = self._effective(moment).get(item_id)
            if current is None:
                raise WorkQueueError("UNKNOWN_ITEM")
            if _held(current, moment):
                raise WorkQueueError("LEASE_LIVE")
            expired = current.get("expired_lease") or {}
            attached = current.get("attached") or {}
            if current["status"] != "READY" or not attached or attached.get("holder") != expired.get("holder"):
                raise WorkQueueError("NOT_RECONCILABLE")
            self._append({"type": "RECONCILE", "item_id": item_id, "observed": observed, "evidence": evidence,
                          "actor": actor, "expired_holder": expired["holder"], "ends": expired["expires_at"],
                          "at": _stamp(moment)})
            status = "DONE" if observed == "COMPLETE_VERIFIED" else "READY"
            return {"item_id": item_id, "status": status, "observed": observed}

    def spawn(self, template, module, now=None) -> dict:
        template_id = _require_token(template, "ITEM")
        module_name = _require_module(module)
        item_id = template_id + "-" + module_name
        if len(item_id) > 64:
            raise WorkQueueError("INVALID_MODULE")
        moment = _now(now)
        with self._lock():
            items = self._effective(moment)
            parent = items.get(template_id)
            if parent is None:
                raise WorkQueueError("UNKNOWN_TEMPLATE")
            if not parent.get("template"):
                raise WorkQueueError("NOT_TEMPLATE")
            current = items.get(item_id)
            if current is not None:
                return _spawn_view(current, idempotent=True)
            child = _child_from_template(parent, item_id, module_name)
            _validate(child, _read_json(self.schema_path, MAX_ITEM_BYTES))
            self._append({
                "type": "SPAWN",
                "template_id": template_id,
                "module": module_name,
                "item_id": item_id,
                "at": _stamp(moment),
            })
            child["result"] = None
            child["released_by"] = None
            return _spawn_view(child, idempotent=False)

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
            if item["status"] == "CLAIMED" and not _held(item, moment) and not item.get("claim_once"):
                # Claimable again, but keep who held it: an expired lease is not proof that the
                # holder's mission stopped, so a consumer must not treat this as a fresh workkey.
                item["expired_lease"] = dict(item["lease"]) if isinstance(item.get("lease"), dict) else None
                item["status"] = "READY"
                item["lease"] = None
        return seeds

    def _append(self, event: dict) -> None:
        line = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        path = self.ledger_path
        if path.is_symlink() or path.parent.is_symlink():
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
        if lock_path.is_symlink() or lock_path.parent.is_symlink():
            raise WorkQueueError("UNREADABLE")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(lock_path, flags, 0o600)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise WorkQueueError("UNREADABLE") from exc
            raise
        try:
            # No first byte is written: Windows locks a range past the end of
            # file, and its byte locks are mandatory, so a write here could
            # land in byte 0 while another claimant holds it.
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
    gate = ""
    if item.get("publish_gate"):
        gate = f"publish_gate: {item['publish_gate']}\n"
    return (
        f"id: {item['id']}\n"
        f"title: {item['title']}\n"
        f"lane: {item['lane']}\n"
        f"branch: {item['branch']}\n"
        f"holder: {holder}\n"
        f"depends_on: {deps}\n"
        f"{gate}"
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

    rcl = sub.add_parser("reclaim")
    rcl.add_argument("--item", required=True)
    rcl.add_argument("--actor", required=True)
    rcl.add_argument("--reason", required=True)

    spawned = sub.add_parser("spawn")
    spawned.add_argument("--template", required=True)
    spawned.add_argument("--module", required=True)

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
        if args.command == "spawn":
            spawned = queue.spawn(args.template, args.module)
            print(json.dumps(spawned, sort_keys=True))
            return 0
        if args.command == "claim":
            claimed = queue.claim(
                args.item, args.holder, args.ttl, host=args.host,
                done_prs=args.done_pr, open_pr_files=args.open_pr_file,
            )
        elif args.command == "reclaim":
            claimed = queue.reclaim(args.item, args.actor, args.reason)
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
    if expected == "boolean":
        return isinstance(value, bool)
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
    if path.is_symlink() or path.parent.is_symlink():
        raise WorkQueueError("UNREADABLE")
    if not path.exists():
        return []
    if not path.is_file():
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
        if not isinstance(event, dict) or event.get("type") not in EVENT_TYPES:
            raise WorkQueueError("UNREADABLE")
        if event["type"] == "SPAWN" and not _valid_spawn_event(event):
            raise WorkQueueError("UNREADABLE")
        if event["type"] in ("ATTACH", "RECLAIM", "RECONCILE", "PARK") and not _valid_recovery_event(event):
            raise WorkQueueError("UNREADABLE")
        events.append(event)
    return events


def _valid_spawn_event(event: dict) -> bool:
    template_id = event.get("template_id")
    module_name = event.get("module")
    if not _event_token(template_id):
        return False
    if not isinstance(module_name, str) or _MODULE.fullmatch(module_name) is None or module_name in (".", ".."):
        return False
    if event.get("item_id") != template_id + "-" + module_name:
        return False
    return _TIME.fullmatch(str(event.get("at") or "")) is not None


def _valid_recovery_event(event: dict) -> bool:
    if not _event_token(event.get("item_id")) or _TIME.fullmatch(str(event.get("at") or "")) is None:
        return False
    if event["type"] == "ATTACH":
        return _event_holder(event.get("holder")) and _event_holder(event.get("ref"))
    if event["type"] == "PARK":
        return _event_holder(event.get("holder")) and _text(event.get("reason"))
    if not _event_holder(event.get("actor")) or not _event_holder(event.get("expired_holder")):
        return False
    ends = event.get("ends")
    if not isinstance(ends, str) or _TIME.fullmatch(ends.removeprefix("parked:")) is None:
        return False
    if event["type"] == "RECLAIM":
        return _text(event.get("reason"))
    return event.get("observed") in RECONCILABLE and _text(event.get("evidence"))


def _child_from_template(parent: dict, item_id: str, module_name: str) -> dict:
    branch = parent["branch"] + "-" + module_name
    title = parent["title"]
    if len(branch) > 200 or len(title) > 200:
        raise WorkQueueError("INVALID_MODULE")
    return {
        "id": item_id,
        "title": title,
        "lane": parent["lane"],
        "branch": branch,
        "files_scope": ["tests/"],
        "depends_on": [],
        "acceptance": list(parent["acceptance"]),
        "provider_hints": list(parent["provider_hints"]),
        "claim_once": True,
        "status": "READY",
        "lease": None,
    }


def _materialize_spawn(items: dict[str, dict], event: dict) -> None:
    item_id = event["item_id"]
    if item_id in items:
        return
    parent = items.get(event["template_id"])
    if parent is None or not parent.get("template"):
        raise WorkQueueError("UNREADABLE")
    child = _child_from_template(parent, item_id, event["module"])
    child["result"] = None
    child["released_by"] = None
    items[item_id] = child


def _spawn_view(item: dict, idempotent: bool) -> dict:
    return {
        "item_id": item["id"],
        "status": item["status"],
        "branch": item["branch"],
        "files_scope": list(item["files_scope"]),
        "claim_once": bool(item.get("claim_once")),
        "idempotent": idempotent,
    }


def _apply(items: dict[str, dict], event: dict) -> None:
    if event["type"] == "SPAWN":
        _materialize_spawn(items, event)
        return
    item = items.get(event.get("item_id"))
    if item is not None and item["status"] == "BLOCKED" and item.get("parked") and event["type"] == "RECLAIM":
        _unpark(item, event)
        return
    if item is None or item["status"] in ("DONE", "BLOCKED") or item.get("template"):
        return
    if _sticky(item) and event["type"] != "RELEASE":
        return
    kind = event["type"]
    if kind == "CLAIM":
        if item.get("claim_once") and item["status"] == "CLAIMED":
            return
        if not _event_holder(event.get("holder")) or not _event_token(event.get("host")):
            raise WorkQueueError("UNREADABLE")
        if _TIME.fullmatch(str(event.get("expires_at") or "")) is None:
            raise WorkQueueError("UNREADABLE")
        if (item.get("lease") or {}).get("holder") != event["holder"]:
            item["attached"] = None
        item["reclaimed"] = None
        item["status"] = "CLAIMED"
        item["lease"] = {"holder": event["holder"], "host": event["host"], "expires_at": event["expires_at"]}
        if event.get("announce") is True:
            item["lease"]["announce"] = True
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
    if kind in ("ATTACH", "RECLAIM", "RECONCILE", "PARK"):
        _apply_recovery(item, event)
        return
    if item["status"] != "CLAIMED" or not isinstance(item.get("lease"), dict):
        return
    result = event.get("result")
    if not isinstance(result, str) or not result.strip() or len(result) > 200 or any(ch in result for ch in "\n\r"):
        raise WorkQueueError("UNREADABLE")
    if not _event_holder(event.get("holder")) or item["lease"]["holder"] != event["holder"]:
        return
    item["status"] = "DONE"
    item["lease"] = None
    item["result"] = result.strip()
    item["released_by"] = event["holder"]


def _apply_recovery(item: dict, event: dict) -> None:
    lease = item.get("lease")
    if item["status"] != "CLAIMED" or not isinstance(lease, dict):
        return
    if event["type"] == "ATTACH":
        if lease["holder"] == event["holder"]:
            item["attached"] = {"holder": event["holder"], "ref": event["ref"]}
        return
    if event["type"] == "PARK":
        if lease["holder"] == event["holder"]:
            item["status"] = "BLOCKED"
            item["lease"] = None
            item["attached"] = None
            item["parked"] = {"holder": event["holder"], "reason": event["reason"], "at": event["at"]}
        return
    # RECLAIM / RECONCILE were checked against an expired lease when written; on replay they
    # end exactly that lease (holder and expiry), so a later RENEW or RELEASE from it no
    # longer applies, and a repeated line cannot end a later lease of the same holder.
    if lease["holder"] != event["expired_holder"] or lease.get("expires_at") != event["ends"]:
        return
    if event["type"] == "RECONCILE" and event["observed"] == "COMPLETE_VERIFIED":
        item["status"] = "DONE"
        item["lease"] = None
        item["result"] = "RECONCILED " + event["evidence"].strip()
        item["released_by"] = "reconcile:" + event["actor"]
        return
    item["status"] = "READY"
    item["lease"] = None
    item["attached"] = None
    item["reclaimed"] = {"from": event["expired_holder"], "actor": event["actor"], "by": event["type"]}


def _unpark(item: dict, event: dict) -> None:
    parked = item["parked"]
    if parked["holder"] != event["expired_holder"] or event["ends"] != "parked:" + parked["at"]:
        return
    item["status"] = "READY"
    item["parked"] = None
    item["reclaimed"] = {"from": parked["holder"], "actor": event["actor"], "by": "RECLAIM"}


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
    if _sticky(item):
        return True
    expires = _parse_time(item["lease"].get("expires_at"))
    return expires is not None and expires > moment


def _sticky(item: dict) -> bool:
    if item.get("pull_request"):
        return item.get("status") == "CLAIMED"
    lease = item.get("lease")
    return item.get("status") == "CLAIMED" and isinstance(lease, dict) and lease.get("expires_at") is None


def _claimable_status(item: dict, moment: datetime) -> bool:
    if item.get("template") or _sticky(item):
        return False
    if item.get("claim_once") and item["status"] == "CLAIMED":
        return False
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
    view = {
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
        "expired_lease": item.get("expired_lease"),
        "attached": None if not item.get("attached") else dict(item["attached"]),
        "reclaimed": None if not item.get("reclaimed") else dict(item["reclaimed"]),
        "parked": None if not item.get("parked") else dict(item["parked"]),
        "publish_gate": item.get("publish_gate"),
        "pull_request": item.get("pull_request"),
        "template": bool(item.get("template")),
        "claim_once": bool(item.get("claim_once")),
    }
    return view


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


def _require_holder(value) -> str:
    if not isinstance(value, str) or _HOLDER.fullmatch(value) is None or len(value) > 80:
        raise WorkQueueError("HOLDER")
    return value


def _require_module(value) -> str:
    if not isinstance(value, str) or _MODULE.fullmatch(value) is None or value in (".", "..") or len(value) > 40:
        raise WorkQueueError("INVALID_MODULE")
    return value


def _require_ttl(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_TTL_SECONDS:
        raise WorkQueueError("TTL")
    return value


def _require_result(value) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 200 or any(ch in value for ch in "\n\r"):
        raise WorkQueueError("RESULT")
    return value.strip()


def _require_text(value, code: str) -> str:
    if not _text(value):
        raise WorkQueueError(code)
    return value.strip()


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 200 and not any(ch in value for ch in "\n\r")


def _event_token(value) -> bool:
    return isinstance(value, str) and _TOKEN.fullmatch(value) is not None and len(value) <= 64


def _event_holder(value) -> bool:
    return isinstance(value, str) and _HOLDER.fullmatch(value) is not None and len(value) <= 80


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
