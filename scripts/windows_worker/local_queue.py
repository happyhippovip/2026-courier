"""One local workkey at a time. No provider calls.

The canonical queue remains courier_core.work_queue. This runner only claims
as the given holder, runs a local function, and releases FINAL after a file
in the workspace verifies. A blocked dependency is not released by skipping
it. A failed item stays claimed and is recorded as dead letter.
"""
import json
import os
from pathlib import Path

from courier_core.work_queue import WorkQueueError, journal_release_proof


class TemporaryFailure(Exception):
    """A local retryable failure. It must not release the workkey."""


def run_once(queue, holder, host, workspace, execute, now, ttl=60, max_attempts=3):
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    if _receipt_log_is_linked(workspace):
        return {
            "outcome": "blocked",
            "reason": "RECEIPT_LINK",
            "receipts": str(workspace / "receipts.jsonl"),
        }
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    held = _held_by(queue, holder, now)
    if len(held) > 1:
        return _receipt(workspace, {"outcome": "blocked", "reason": "MULTIPLE_HELD"})
    if held:
        item_id = held[0]["id"]
        queue.renew(item_id, holder, ttl, now=now)
        _append(workspace, "CLAIM", {"item_id": item_id, "holder": holder, "resumed": True})
    else:
        ready = queue.list_ready(now=now)
        if not ready:
            return _receipt(workspace, {"outcome": "idle", "next": []})
        item_id = ready[0]["id"]
        try:
            claimed = queue.claim(item_id, holder, ttl, host=host, now=now)
        except WorkQueueError as exc:
            return _receipt(workspace, {"outcome": "blocked", "reason": exc.code, "item_id": item_id})
        if claimed["holder"] != holder:
            return _receipt(workspace, {"outcome": "blocked", "reason": "NOT_OWNER", "item_id": item_id})
        _append(workspace, "CLAIM", {"item_id": item_id, "holder": holder, "resumed": False})

    phase = _read_json(workspace / "phase.json", {})
    if phase.get("item_id") not in (None, item_id):
        if phase.get("phase") != "FINAL":
            return _receipt(workspace, {"outcome": "blocked", "reason": "PHASE_MISMATCH", "item_id": item_id})
        phase = {}
    if phase.get("item_id") != item_id:
        phase = {"item_id": item_id, "phase": "CLAIMED"}
        _write_json(workspace / "phase.json", phase)

    evidence = phase.get("evidence") if phase.get("item_id") == item_id and phase.get("phase") == "RAN" else None
    if evidence is None:
        attempts = _attempts(workspace, item_id)
        if attempts >= max_attempts:
            return _dead(workspace, item_id, holder, "ATTEMPTS_EXHAUSTED", attempts)
        while True:
            if kill_switch_engaged(workspace):
                return _receipt(workspace, {"outcome": "killed", "item_id": item_id})
            try:
                produced = execute(item_id, workspace)
            except TemporaryFailure:
                attempts += 1
                _write_json(workspace / "attempts.json", {"item_id": item_id, "attempts": attempts})
                _append(workspace, "RETRY", {"item_id": item_id, "attempts": attempts})
                if attempts >= max_attempts:
                    return _dead(workspace, item_id, holder, "ATTEMPTS_EXHAUSTED", attempts)
                continue
            evidence = str(produced)
            _write_json(workspace / "phase.json", {"item_id": item_id, "phase": "RAN", "evidence": evidence})
            _append(workspace, "RUN", {"item_id": item_id, "evidence": evidence})
            break

    if not _verified(workspace, evidence):
        return _dead(workspace, item_id, holder, "UNVERIFIED", _attempts(workspace, item_id))
    _append(workspace, "VERIFY", {"item_id": item_id, "evidence": evidence})
    # P2 R2: a local file check is no proof. DONE needs the journal RESULT_ACCEPTED of this workkey.
    proof = journal_release_proof(getattr(queue, "journal", None), item_id)
    released = queue.release(item_id, holder, "FINAL", now=now, proof=proof)
    if released["status"] != "DONE" or released["result"] != "FINAL":
        return _receipt(workspace, {"outcome": "blocked", "reason": "RELEASE_REJECTED", "item_id": item_id})
    _write_json(workspace / "phase.json", {"item_id": item_id, "phase": "FINAL", "evidence": evidence})
    attempts_path = workspace / "attempts.json"
    if attempts_path.exists():
        attempts_path.unlink()
    nxt = [item["id"] for item in queue.list_ready(now=now)]
    _append(workspace, "FINAL", {"item_id": item_id})
    _append(workspace, "NEXT", {"item_id": item_id, "next": nxt})
    return _receipt(workspace, {"outcome": "final", "item_id": item_id, "next": nxt})


def heartbeat(workspace):
    """Record liveness. This is not a verified result and never releases work."""
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    _write_json(workspace / "health.json", {"status": "alive", "verified": False})
    return {"outcome": "alive", "verified": False}


def kill_switch_engaged(workspace):
    return (Path(workspace) / "KILL").is_file()


def backoff_seconds(attempt, base=10, cap=300):
    """Bounded pause after a temporary failure. The cap is the daemon's max."""
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 0:
        raise ValueError("attempt must be a non-negative integer")
    if base < 1 or cap < base:
        raise ValueError("backoff bounds are invalid")
    delay = base
    for _ in range(attempt):
        delay = min(cap, delay * 2)
    return delay


def run_until_idle(queue, holder, host, workspace, execute, now, ttl=60, max_attempts=3, limit=20):
    """Release verified workkeys in deterministic order, then stop.

    A KILL file stops the loop before the next claim. Heartbeats stay unverified.
    """
    receipts = []
    for _ in range(limit):
        if kill_switch_engaged(workspace):
            receipts.append({"outcome": "killed"})
            break
        heartbeat(workspace)
        receipt = run_once(queue, holder, host, workspace, execute, now, ttl=ttl, max_attempts=max_attempts)
        receipts.append(receipt)
        if receipt["outcome"] != "final":
            break
    else:
        receipts.append({"outcome": "blocked", "reason": "STEP_LIMIT"})
    return receipts


def _held_by(queue, holder, now):
    return [
        item for item in queue.items(now=now)
        if item["status"] == "CLAIMED" and isinstance(item.get("lease"), dict) and item["lease"].get("holder") == holder
    ]


def _attempts(workspace, item_id):
    data = _read_json(workspace / "attempts.json", {})
    if data.get("item_id") != item_id:
        return 0
    try:
        return int(data.get("attempts") or 0)
    except (TypeError, ValueError):
        return 0


def _verified(workspace, evidence):
    if not isinstance(evidence, str) or not evidence or ".." in Path(evidence).parts:
        return False
    path = Path(evidence)
    if not path.is_absolute():
        path = workspace / path
    try:
        resolved = path.resolve()
        root = workspace.resolve()
    except OSError:
        return False
    if resolved != root and root not in resolved.parents:
        return False
    if path.is_symlink() or not path.is_file():
        return False
    try:
        return path.stat().st_size > 0
    except OSError:
        return False


def _receipt_log_is_linked(workspace):
    return (workspace / "receipts.jsonl").is_symlink() or (workspace / "dead_letter.jsonl").is_symlink()


def _open_append(path):
    if path.is_symlink():
        raise OSError(f"{path}: refusing to follow a symlink")
    return path.open("a", encoding="utf-8")


def _dead(workspace, item_id, holder, reason, attempts):
    line = json.dumps({
        "item_id": item_id,
        "holder": holder,
        "reason": reason,
        "attempts": attempts,
    }, sort_keys=True)
    with _open_append(workspace / "dead_letter.jsonl") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    _append(workspace, "DEAD_LETTER", {"item_id": item_id, "reason": reason})
    return _receipt(workspace, {
        "outcome": "dead_letter",
        "item_id": item_id,
        "reason": reason,
        "attempts": attempts,
    })


def _append(workspace, step, fields):
    record = {"step": step, **fields}
    with _open_append(workspace / "receipts.jsonl") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _receipt(workspace, body):
    body["receipts"] = str(workspace / "receipts.jsonl")
    return body


def _read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeError, OSError):
        return default


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)
