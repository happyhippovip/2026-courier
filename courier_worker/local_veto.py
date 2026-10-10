"""Local host veto: a host may refuse a work item before it accepts it.

The decision is ACCEPT or VETO. A veto records a receipt and returns the item
to the queue so another host can take it. It is not a failure of the work.

Rules, first match wins:

1. host config unreadable (fail closed)
2. user pause file present
3. governor read-only health is RESOURCE_PAUSE
4. named provider is not installed or not logged in
5. files_scope touches a path listed in the local protected-paths file
6. current time is inside the quiet-hours window

The governor is read only. This module never calls ``admit_job``,
``measure_pressure``, ``trigger_quiesce``, ``read_metrics``, or ``classify``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Optional, Protocol

ACCEPT = "ACCEPT"
VETO = "VETO"

USER_PAUSE = "user_pause"
RESOURCE_PAUSE = "resource_pause"
PROVIDER_UNAVAILABLE = "provider_unavailable"
PROTECTED_PATH = "protected_path"
QUIET_HOURS = "quiet_hours"
CONFIG_UNREADABLE = "config_unreadable"

_RESOURCE_PAUSE_HEALTH = "RESOURCE_PAUSE"
_PROVIDER_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


class ConfigUnreadable(Exception):
    """Host configuration could not be read. The host must not accept work."""


class WorkQueue(Protocol):
    def claim(self, worker_id: str) -> Optional[dict]:
        """Return the next item for this host, or None when the queue is empty."""

    def release(self, item: dict) -> None:
        """Return an item to the queue. Do not mark it failed."""


@dataclass(frozen=True)
class Verdict:
    decision: str
    reason_code: str = ""
    detail: str = ""
    path_hashes: tuple = ()

    def __str__(self) -> str:
        if self.decision == ACCEPT:
            return ACCEPT
        return f"VETO({self.reason_code}, {self.detail})"


def accept(detail: str = "") -> Verdict:
    return Verdict(ACCEPT, "", detail, ())


def veto(reason_code: str, detail: str, paths: tuple = ()) -> Verdict:
    return Verdict(VETO, reason_code, detail, tuple(sorted(set(paths))))


def hash_path(path: str) -> str:
    """sha256 of the normalized path. The path text is not returned."""
    normalized = os.path.normpath(path)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return "sha256:" + digest


def read_governor_health(governor: Any = None) -> str:
    """Read host health without changing governor state.

    Uses ``health()`` when the object provides it, otherwise the ``state``
    attribute. Both are read-only. A missing or non-string value fails closed.
    """
    if governor is None:
        from scripts.resource_governor import governor as live
        governor = live
    health_fn = getattr(governor, "health", None)
    try:
        if callable(health_fn):
            value = health_fn()
        else:
            value = getattr(governor, "state", None)
    except Exception as exc:
        raise ConfigUnreadable("governor health unreadable") from exc
    if not isinstance(value, str) or not value:
        raise ConfigUnreadable("governor health unreadable")
    return value


def evaluate(item: Any, *, config_path: str, governor: Any = None,
             now: Optional[datetime] = None) -> Verdict:
    """Return ACCEPT or VETO(reason_code, detail). Same inputs, same verdict."""
    try:
        config = _load_config(config_path)
        return _decide(item, config, config_path, governor, now)
    except ConfigUnreadable:
        paths = (hash_path(config_path),) if isinstance(config_path, str) and config_path else ()
        return veto(CONFIG_UNREADABLE, "host config is unreadable", paths)


def consider(queue: WorkQueue, worker_id: str, *, config_path: str, receipt_dir: str,
             governor: Any = None, now: Optional[datetime] = None) -> tuple:
    """Take one item. A veto is recorded and the item is released, not failed.

    An ACCEPT also releases the item back to the queue so the host claim
    path can take it and run it; the returned ``item`` only names what was
    accepted. Returns ``(verdict, item)``. ``item`` is set only for ACCEPT.
    An empty queue is ``(ACCEPT, None)``. A veto is ``(VETO(...), None)``
    after release.
    """
    item = queue.claim(worker_id)
    if item is None:
        return accept("no work item"), None
    verdict = evaluate(item, config_path=config_path, governor=governor, now=now)
    if verdict.decision == VETO:
        try:
            record_receipt(receipt_dir, item, verdict, worker_id=worker_id, now=now)
        finally:
            queue.release(item)
        return verdict, None
    queue.release(item)
    return verdict, item


def record_receipt(receipt_dir: str, item: Any, verdict: Verdict, *,
                   worker_id: str, now: Optional[datetime] = None) -> dict:
    """Write one receipt-shaped JSON object. No secrets and no raw paths."""
    if verdict.decision != VETO:
        raise ValueError("only a veto is recorded")
    receipt = receipt_body(item, verdict, worker_id=worker_id, now=now)
    directory = Path(receipt_dir)
    directory.mkdir(parents=True, exist_ok=True)
    dispatch_id = receipt["dispatch_id"] or "unknown"
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in dispatch_id) or "unknown"
    path = directory / f"local-veto-{safe}.json"
    _atomic_json(path, receipt)
    return receipt


def receipt_body(item: Any, verdict: Verdict, *, worker_id: str,
                 now: Optional[datetime] = None) -> dict:
    source = item if isinstance(item, dict) else {}
    when = _as_utc(now) if now is not None else datetime.now(timezone.utc)
    return {
        "schema": "courier.local_veto.v1",
        "decision": VETO,
        "reason_code": verdict.reason_code,
        "detail": verdict.detail,
        "dispatch_id": _short_id(source.get("dispatch_id")),
        "task_id": _short_id(source.get("task_id")),
        "worker_id": _short_id(worker_id),
        "path_hashes": list(verdict.path_hashes),
        "recorded_at": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _decide(item: Any, config: dict, config_path: str, governor: Any,
            now: Optional[datetime]) -> Verdict:
    if not isinstance(item, dict):
        return veto(CONFIG_UNREADABLE, "work item is unreadable", (hash_path(config_path),))

    pause = config.get("pause_file")
    if pause is not None:
        if not isinstance(pause, str) or not pause:
            raise ConfigUnreadable("pause file path is unreadable")
        try:
            present = os.path.lexists(pause)
        except OSError as exc:
            raise ConfigUnreadable("pause file is unreadable") from exc
        if present:
            return veto(USER_PAUSE, "user pause file is present", (hash_path(pause),))

    if read_governor_health(governor) == _RESOURCE_PAUSE_HEALTH:
        return veto(RESOURCE_PAUSE, "host is in RESOURCE_PAUSE")

    provider = item.get("provider")
    if provider is not None:
        verdict = _provider_verdict(provider, config)
        if verdict is not None:
            return verdict

    scope = item.get("files_scope")
    if scope is not None:
        verdict = _protected_verdict(scope, config)
        if verdict is not None:
            return verdict

    quiet = config.get("quiet_hours")
    if quiet is not None:
        verdict = _quiet_verdict(quiet, now)
        if verdict is not None:
            return verdict

    return accept()


def _provider_verdict(provider: Any, config: dict) -> Optional[Verdict]:
    if not isinstance(provider, str) or not provider:
        raise ConfigUnreadable("provider name is unreadable")
    providers = config.get("providers")
    if not isinstance(providers, dict):
        raise ConfigUnreadable("provider list is unreadable")
    record = providers.get(provider)
    if not isinstance(record, dict):
        return veto(PROVIDER_UNAVAILABLE, _provider_detail(provider, "not installed"))
    if record.get("installed") is not True:
        return veto(PROVIDER_UNAVAILABLE, _provider_detail(provider, "not installed"))
    if record.get("logged_in") is not True:
        return veto(PROVIDER_UNAVAILABLE, _provider_detail(provider, "not logged in"))
    return None


def _provider_detail(provider: str, state: str) -> str:
    if _PROVIDER_ID.match(provider):
        return f"provider {provider} is {state}"
    return f"provider is {state}"


def _protected_verdict(scope: Any, config: dict) -> Optional[Verdict]:
    if not isinstance(scope, list) or any(not isinstance(entry, str) or not entry for entry in scope):
        raise ConfigUnreadable("files_scope is unreadable")
    listed = config.get("protected_paths_file")
    if listed is None:
        return None
    if not isinstance(listed, str) or not listed:
        raise ConfigUnreadable("protected paths file is unreadable")
    protected = _read_protected_paths(listed)
    hashes = []
    for entry in scope:
        for guarded in protected:
            if _touches(entry, guarded):
                hashes.append(hash_path(entry))
                hashes.append(hash_path(guarded))
    if hashes:
        return veto(PROTECTED_PATH, "files_scope touches a protected path", tuple(hashes))
    return None


def _quiet_verdict(quiet: Any, now: Optional[datetime]) -> Optional[Verdict]:
    if not isinstance(quiet, dict):
        raise ConfigUnreadable("quiet hours are unreadable")
    start = _parse_hhmm(quiet.get("start"))
    end = _parse_hhmm(quiet.get("end"))
    zone = quiet.get("tz", "UTC")
    if zone not in ("UTC", "Z", "+00:00"):
        raise ConfigUnreadable("quiet hours timezone is unreadable")
    moment = _as_utc(now) if now is not None else datetime.now(timezone.utc)
    if _inside_window(moment.time(), start, end):
        return veto(QUIET_HOURS, f"current time is inside quiet hours {quiet['start']}-{quiet['end']}")
    return None


def _load_config(path: str) -> dict:
    if not isinstance(path, str) or not path:
        raise ConfigUnreadable("host config path is empty")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigUnreadable("host config is unreadable") from exc
    if not isinstance(data, dict):
        raise ConfigUnreadable("host config is unreadable")
    return data


def _read_protected_paths(path: str) -> tuple:
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, UnicodeError) as exc:
        raise ConfigUnreadable("protected paths file is unreadable") from exc
    found = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        found.append(line)
    return tuple(found)


def _touches(scope: str, protected: str) -> bool:
    left = Path(os.path.normpath(scope)).parts
    right = Path(os.path.normpath(protected)).parts
    if not left or not right:
        return False
    if left == right:
        return True
    if len(left) > len(right) and left[:len(right)] == right:
        return True
    if len(right) > len(left) and right[:len(left)] == left:
        return True
    return False


def _parse_hhmm(value: Any) -> time:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        raise ConfigUnreadable("quiet hours are unreadable")
    hour, minute = value[:2], value[3:]
    if not (hour.isdigit() and minute.isdigit()):
        raise ConfigUnreadable("quiet hours are unreadable")
    h, m = int(hour), int(minute)
    if h > 23 or m > 59:
        raise ConfigUnreadable("quiet hours are unreadable")
    return time(h, m)


def _inside_window(moment: time, start: time, end: time) -> bool:
    if start == end:
        return False
    if start < end:
        return start <= moment < end
    return moment >= start or moment < end


def _as_utc(moment: datetime) -> datetime:
    if not isinstance(moment, datetime):
        raise ConfigUnreadable("clock is unreadable")
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _short_id(value: Any) -> str:
    if isinstance(value, str) and value and len(value) <= 200 and "\n" not in value and "/" not in value:
        return value
    return ""


def _atomic_json(path: Path, payload: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
