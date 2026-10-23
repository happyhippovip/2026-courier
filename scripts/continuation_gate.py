"""One continuation per fingerprint. This module sends no prompt.

A fingerprint is head|workkey|sha. Unknown cost is never stored as 0.
A stale sender lease is not taken over. The product logon task is not this gate.
"""
import json
import os
import time
from pathlib import Path

SCHEMA = 1
ABSOLUTE_LIMIT_SECONDS = 3600
MAX_FOLLOWUPS = 5
_UNKNOWN_CLASSES = {"unknown", "unknown_cost"}


def fingerprint(head, workkey, sha):
    for part in (head, workkey, sha):
        if not isinstance(part, str) or part == "" or "|" in part or "\n" in part:
            raise ValueError("fingerprint part is invalid")
    return head + "|" + workkey + "|" + sha


def evaluate(
    root,
    *,
    head,
    workkey,
    sha,
    sender,
    now,
    session="completed",
    proof=None,
    cost_eur=None,
    cost_class=None,
    quota_remaining=None,
    ttl=60,
):
    """Return whether this sender may start one continuation. Never starts it."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if _killed(root):
        return _decision("killed", None)
    if not _known_cost(cost_eur, cost_class):
        return _decision("unknown_cost", None)
    quota = _quota(quota_remaining)
    if quota != "open":
        return _decision("quota_pause", None, reason=quota)
    if session not in {"completed", "aborted"}:
        return _decision("blocked", None, reason="SESSION")
    if not isinstance(sender, str) or sender == "" or not _epoch(now) or not _ttl(ttl):
        return _decision("blocked", None, reason="SENDER")
    mark = fingerprint(head, workkey, sha)
    acquired, lock = _acquire_mutex(root)
    if not acquired:
        return _decision("blocked", mark, reason="BUSY")
    try:
        return _evaluate_locked(root, head, mark, sender, now, session, proof, ttl)
    finally:
        _release_mutex(lock)


def complete(root, *, sender, now, head, workkey, sha, proof, ttl=60):
    """Record one proven fingerprint. An empty proof does not complete it."""
    root = Path(root)
    mark = fingerprint(head, workkey, sha)
    if not _proof(proof):
        return _decision("blocked", mark, reason="PROOF")
    if not isinstance(sender, str) or sender == "" or not _epoch(now):
        return _decision("blocked", mark, reason="SENDER")
    acquired, lock = _acquire_mutex(root)
    if not acquired:
        return _decision("blocked", mark, reason="BUSY")
    try:
        lease = _lease(root, sender, now, ttl)
        if lease != "acquired":
            return _decision(lease, mark)
        state = _load(root)
        if state is None:
            return _decision("blocked", mark, reason="CHECKPOINT")
        if mark not in state["pending"]:
            return _decision("unchanged" if mark in state["completed"] else "blocked", mark)
        state["pending"].remove(mark)
        state["completed"].append(mark)
        _save(root, state)
        return _decision("unchanged", mark)
    finally:
        _release_mutex(lock)


def _evaluate_locked(root, head, mark, sender, now, session, proof, ttl):
    lease = _lease(root, sender, now, ttl)
    if lease != "acquired":
        return _decision(lease, mark)
    state = _load(root)
    if state is None:
        return _decision("blocked", mark, reason="CHECKPOINT")
    if state["head"] not in (None, head):
        state["head"] = head
        state["started_at"] = None
        state["followups"] = 0
    elif state["head"] is None:
        state["head"] = head
    if _past_limit(state, now) or state["followups"] >= MAX_FOLLOWUPS:
        _save(root, state)
        return _decision("limit", mark)
    if mark in state["aborted"] or (session == "aborted" and not _proof(proof)):
        if mark not in state["aborted"]:
            state["aborted"].append(mark)
            _save(root, state)
        return _decision("aborted_no_replay", mark)
    if mark in state["completed"]:
        return _decision("unchanged", mark)
    if mark in state["pending"]:
        return _decision("duplicate", mark)
    if session == "aborted":
        state["completed"].append(mark)
        _save(root, state)
        return _decision("unchanged", mark)
    state["pending"].append(mark)
    state["followups"] += 1
    if state["started_at"] is None:
        state["started_at"] = now
    _save(root, state)
    return _decision("admit", mark, executions=1)


def _acquire_mutex(root):
    path = root / "critical.lock"
    if path.is_symlink():
        return False, path
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            continue
        else:
            os.close(handle)
            return True, path
    return False, path


def _release_mutex(path):
    if path is None or path.is_symlink():
        return
    try:
        path.unlink()
    except OSError:
        return


def _decision(outcome, mark, executions=0, reason=None):
    body = {"outcome": outcome, "fingerprint": mark, "executions": executions}
    if reason is not None:
        body["reason"] = reason
    return body


def _known_cost(cost_eur, cost_class):
    if isinstance(cost_eur, bool) or not isinstance(cost_eur, (int, float)):
        return False
    if cost_eur != cost_eur or cost_eur < 0 or cost_eur == float("inf"):
        return False
    if not isinstance(cost_class, str):
        return False
    label = cost_class.strip().lower()
    return label != "" and label not in _UNKNOWN_CLASSES


def _quota(quota_remaining):
    if isinstance(quota_remaining, bool) or not isinstance(quota_remaining, int):
        return "QUOTA_UNKNOWN"
    if quota_remaining < 0:
        return "QUOTA_UNKNOWN"
    if quota_remaining == 0:
        return "QUOTA_EXHAUSTED"
    return "open"


def _proof(proof):
    return isinstance(proof, str) and proof.strip() != "" and "\n" not in proof


def _epoch(now):
    return isinstance(now, int) and not isinstance(now, bool) and now >= 0


def _ttl(ttl):
    return isinstance(ttl, int) and not isinstance(ttl, bool) and ttl > 0


def _killed(root):
    return (root / "KILL").is_file()


def _past_limit(state, now):
    started = state.get("started_at")
    return isinstance(started, int) and now >= started + ABSOLUTE_LIMIT_SECONDS


def _lease(root, sender, now, ttl):
    path = root / "sender.lock"
    if path.is_symlink():
        return "blocked"
    if not path.exists():
        payload = json.dumps({"sender": sender, "until": now + ttl}, sort_keys=True).encode("utf-8")
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            return _read_lease(path, sender, now, ttl)
        else:
            try:
                os.write(handle, payload)
            finally:
                os.close(handle)
            return "acquired"
    return _read_lease(path, sender, now, ttl)


def _read_lease(path, sender, now, ttl):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return "stale_lease"
    holder = data.get("sender")
    until = data.get("until")
    if not isinstance(holder, str) or isinstance(until, bool) or not isinstance(until, int):
        return "stale_lease"
    if until <= now:
        return "stale_lease"
    if holder != sender:
        return "duplicate_sender"
    _atomic_write(path, {"sender": sender, "until": now + ttl})
    return "acquired"


def _load(root):
    path = root / "checkpoint.json"
    if path.is_symlink():
        return None
    if not path.exists():
        return {
            "schema": SCHEMA,
            "head": None,
            "completed": [],
            "pending": [],
            "aborted": [],
            "started_at": None,
            "followups": 0,
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if data.get("schema") != SCHEMA:
        return None
    for key in ("completed", "pending", "aborted"):
        if not isinstance(data.get(key), list):
            return None
    if data.get("followups") is None:
        data["followups"] = 0
    if isinstance(data.get("followups"), bool) or not isinstance(data.get("followups"), int):
        return None
    return data


def _save(root, state):
    state["schema"] = SCHEMA
    _atomic_write(root / "checkpoint.json", state)


def _atomic_write(path, data):
    if path.is_symlink():
        raise OSError(f"{path}: refusing to follow a symlink")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)
