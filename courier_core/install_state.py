"""Cross-platform install state contract.

A platform installer records evidence. This module derives one status from
that evidence and writes the install journal. It does not start, stop, or
signal a worker, and it does not talk to the controller.

States
------
NOT_INSTALLED
    No journal, or an explicit uninstall.
INSTALLING
    ``begin`` has been recorded and the interrupt timeout has not elapsed.
INSTALLED_UNVERIFIED
    A completed install whose process identity matches, but the controller
    has not confirmed this worker since install finished inside the freshness
    window. A live process alone is never HEALTHY.
HEALTHY
    Completed install, config path present, runtime present, scheduler
    registered as the current user (never SYSTEM or root), process identity
    matches (pid, start time, executable), and controller confirmation is
    newer than install finish and still fresh.
REPAIR_REQUIRED
    A completed install is missing a component, the process identity does not
    match, or an install was left in INSTALLING past the interrupt timeout.
    Interrupted installs are REPAIR_REQUIRED, not FAILED.
FAILED
    ``fail`` was called. The reason code is the one the installer recorded.

The journal is one JSON object published with a temp file and ``os.replace``.
``begin`` of the same version while that install is already in progress is a
no-op. An upgrade stashes the completed marker as ``previous`` so ``rollback``
can restore it. User project and data directories named in ``protected_dirs``
are never deleted.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "1"
JOURNAL_NAME = "install_journal.json"
MAX_STATE_BYTES = 1024 * 1024

NOT_INSTALLED = "NOT_INSTALLED"
INSTALLING = "INSTALLING"
INSTALLED_UNVERIFIED = "INSTALLED_UNVERIFIED"
HEALTHY = "HEALTHY"
REPAIR_REQUIRED = "REPAIR_REQUIRED"
FAILED = "FAILED"

STATES = (
    NOT_INSTALLED,
    INSTALLING,
    INSTALLED_UNVERIFIED,
    HEALTHY,
    REPAIR_REQUIRED,
    FAILED,
)

REFUSED_RUNNING_WORKER = "REFUSED_RUNNING_WORKER"
SECRET_REJECTED = "SECRET_REJECTED"
JOURNAL_UNREADABLE = "JOURNAL_UNREADABLE"
NO_PREVIOUS_VERSION = "NO_PREVIOUS_VERSION"
INSTALL_IN_PROGRESS = "INSTALL_IN_PROGRESS"
INTERRUPTED_INSTALL = "INTERRUPTED_INSTALL"
CONTROLLER_UNCONFIRMED = "CONTROLLER_UNCONFIRMED"
CONTROLLER_STALE = "CONTROLLER_STALE"

INTERRUPT_TIMEOUT_S = 15 * 60
CONFIRMATION_FRESHNESS_S = 120
REDACTED = "[redacted]"
PRIVILEGED_PRINCIPALS = frozenset({"system", "root"})
PROTECTED_DIRS = ("projects", "data")

_FORBIDDEN_PARTS = frozenset({"token", "secret", "password", "apikey"})
_BEARER = re.compile(r"(?i)\bbearer\s+[a-z0-9\-._~+/]{8,}={0,2}")


class SecretRejected(ValueError):
    """A document carries a secret field or a bearer token."""


class JournalUnreadable(ValueError):
    """The journal file exists but is not a JSON object."""


@dataclass(frozen=True)
class JournalResult:
    ok: bool
    reason: str | None
    journal: dict | None


@dataclass(frozen=True)
class Evidence:
    """Observed facts. Paths are presence flags plus path strings, never file contents."""

    config_present: bool = False
    runtime_present: bool = False
    scheduler_registered: bool = False
    scheduler_principal: str | None = None
    current_user: str | None = None
    process_alive: bool = False
    process_identity: Mapping[str, Any] | None = None
    controller_worker_id: str | None = None
    controller_confirmed_at: datetime | None = None


def reject_secrets(document: Any) -> None:
    """Raise SecretRejected when a key or bearer-token value would leak."""
    if _has_secret(document):
        raise SecretRejected("document contains a secret field or bearer token")


def scrub_secrets(document: Any) -> Any:
    """Return a copy with secret keys and bearer-token values replaced."""
    if isinstance(document, Mapping):
        cleaned = {}
        for key, value in document.items():
            if _key_forbidden(str(key)):
                cleaned[str(key)] = REDACTED
            else:
                cleaned[str(key)] = scrub_secrets(value)
        return cleaned
    if isinstance(document, list):
        return [scrub_secrets(item) for item in document]
    if isinstance(document, str) and _BEARER.search(document):
        return REDACTED
    return document


def status_from_dir(
    state_dir: str | os.PathLike,
    evidence: Evidence,
    now: datetime,
    *,
    interrupt_timeout_s: float = INTERRUPT_TIMEOUT_S,
    confirmation_freshness_s: float = CONFIRMATION_FRESHNESS_S,
) -> dict[str, Any]:
    """Hub-facing read. An unreadable journal is repair, never a silent success."""
    try:
        document = InstallJournal(state_dir).load()
    except JournalUnreadable:
        return _status(REPAIR_REQUIRED, now, version=None, reason_code=JOURNAL_UNREADABLE, worker_id=None)
    return derive_state(
        document, evidence, now,
        interrupt_timeout_s=interrupt_timeout_s,
        confirmation_freshness_s=confirmation_freshness_s,
    )


def derive_state(
    journal: Mapping[str, Any] | None,
    evidence: Evidence,
    now: datetime,
    *,
    interrupt_timeout_s: float = INTERRUPT_TIMEOUT_S,
    confirmation_freshness_s: float = CONFIRMATION_FRESHNESS_S,
) -> dict[str, Any]:
    """Derive install status from a journal snapshot and current evidence."""
    _require_aware(now)
    if journal is None or journal.get("phase") in (None, "uninstalled"):
        return _status(NOT_INSTALLED, now, version=None, reason_code=None, worker_id=None)
    if journal.get("phase") == "failed":
        return _status(
            FAILED, now,
            version=journal.get("version"),
            reason_code=journal.get("failure_reason") or "FAILED",
            worker_id=None,
        )
    if journal.get("phase") == "installing":
        started = _parse_time(journal.get("started_at"))
        if started is None or now - started > timedelta(seconds=interrupt_timeout_s):
            return _status(
                REPAIR_REQUIRED, now,
                version=journal.get("version"),
                reason_code=INTERRUPTED_INSTALL,
                worker_id=None,
            )
        return _status(INSTALLING, now, version=journal.get("version"), reason_code=None, worker_id=None)
    if journal.get("phase") != "complete" or not journal.get("finished_at"):
        return _status(
            REPAIR_REQUIRED, now,
            version=journal.get("version"),
            reason_code=JOURNAL_UNREADABLE,
            worker_id=None,
        )
    gap = _completed_gap(journal, evidence, now, confirmation_freshness_s)
    if gap is None:
        return _status(
            HEALTHY, now,
            version=journal.get("version"),
            reason_code=None,
            worker_id=evidence.controller_worker_id,
        )
    if gap in (CONTROLLER_UNCONFIRMED, CONTROLLER_STALE):
        return _status(
            INSTALLED_UNVERIFIED, now,
            version=journal.get("version"),
            reason_code=gap,
            worker_id=None,
        )
    return _status(
        REPAIR_REQUIRED, now,
        version=journal.get("version"),
        reason_code=gap,
        worker_id=None,
    )


class InstallJournal:
    """Atomic, idempotent install journal under a caller-supplied state directory."""

    def __init__(self, state_dir: str | os.PathLike):
        self.state_dir = Path(state_dir)
        self.path = self.state_dir / JOURNAL_NAME

    def load(self) -> dict | None:
        if not self.path.exists():
            return None
        try:
            document = json.loads(_read_capped(self.path).decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise JournalUnreadable("unreadable") from exc
        if not isinstance(document, dict):
            raise JournalUnreadable("unreadable")
        return document

    def begin(
        self,
        version: str,
        now: datetime,
        *,
        running_worker: Mapping[str, Any] | None = None,
        config_path: str | None = None,
        runtime_path: str | None = None,
        protected_dirs: tuple[str, ...] | list[str] = PROTECTED_DIRS,
    ) -> JournalResult:
        """Start an install. Refuse a live worker this journal cannot attribute."""
        _require_version(version)
        _require_aware(now)
        existing, refused = self._existing()
        if refused is not None:
            return refused
        if not _worker_attributable(existing, running_worker):
            return JournalResult(False, REFUSED_RUNNING_WORKER, existing)
        if existing and existing.get("phase") == "installing" and existing.get("version") == version:
            return JournalResult(True, None, existing)
        if existing and existing.get("phase") == "installing" and existing.get("version") != version:
            return JournalResult(False, INSTALL_IN_PROGRESS, existing)
        previous = _previous_marker(existing, version)
        document = {
            "schema_version": SCHEMA_VERSION,
            "phase": "installing",
            "version": version,
            "previous": previous,
            "started_at": _iso(now),
            "finished_at": None,
            "phases": [],
            "failure_reason": None,
            "config_path": config_path if config_path is not None else (existing or {}).get("config_path"),
            "runtime_path": runtime_path if runtime_path is not None else (existing or {}).get("runtime_path"),
            "process_identity": None,
            "protected_dirs": _protected(protected_dirs, existing),
        }
        return self._publish(document)

    def phase(self, name: str, now: datetime, *, detail: Mapping[str, Any] | None = None) -> JournalResult:
        _require_aware(now)
        if not name or not isinstance(name, str):
            raise ValueError("phase name is required")
        existing, refused = self._existing()
        if refused is not None:
            return refused
        if existing is None or existing.get("phase") != "installing":
            return JournalResult(False, INSTALL_IN_PROGRESS, existing)
        phases = list(existing.get("phases") or [])
        if phases and phases[-1].get("name") == name:
            return JournalResult(True, None, existing)
        entry: dict[str, Any] = {"name": name, "at": _iso(now)}
        if detail:
            entry["detail"] = scrub_secrets(dict(detail))
        phases.append(entry)
        updated = dict(existing)
        updated["phases"] = phases
        return self._publish(updated)

    def complete(self, now: datetime, *, process_identity: Mapping[str, Any] | None = None) -> JournalResult:
        _require_aware(now)
        existing, refused = self._existing()
        if refused is not None:
            return refused
        if existing is None:
            return JournalResult(False, INSTALL_IN_PROGRESS, None)
        if existing.get("phase") == "complete" and existing.get("finished_at"):
            return JournalResult(True, None, existing)
        if existing.get("phase") != "installing":
            return JournalResult(False, INSTALL_IN_PROGRESS, existing)
        updated = dict(existing)
        updated["phase"] = "complete"
        updated["finished_at"] = _iso(now)
        updated["failure_reason"] = None
        if process_identity is not None:
            updated["process_identity"] = _identity(process_identity)
        return self._publish(updated)

    def fail(self, reason_code: str, now: datetime) -> JournalResult:
        _require_aware(now)
        if not reason_code or not isinstance(reason_code, str):
            raise ValueError("failure reason code is required")
        reject_secrets({"reason_code": reason_code})
        existing, refused = self._existing()
        if refused is not None:
            return refused
        if existing and existing.get("phase") == "failed" and existing.get("failure_reason") == reason_code:
            return JournalResult(True, None, existing)
        if existing is None or existing.get("phase") != "installing":
            return JournalResult(False, INSTALL_IN_PROGRESS, existing)
        updated = dict(existing)
        updated["phase"] = "failed"
        updated["finished_at"] = _iso(now)
        updated["failure_reason"] = reason_code
        return self._publish(updated)

    def rollback(self, now: datetime) -> JournalResult:
        """Restore the previous completed version marker. Does not launch a worker."""
        _require_aware(now)
        existing, refused = self._existing()
        if refused is not None:
            return refused
        previous = (existing or {}).get("previous") if existing else None
        if not isinstance(previous, dict) or not previous.get("version"):
            return JournalResult(False, NO_PREVIOUS_VERSION, existing)
        restored = {
            "schema_version": SCHEMA_VERSION,
            "phase": "complete",
            "version": previous["version"],
            "previous": None,
            "started_at": previous.get("started_at"),
            "finished_at": previous.get("finished_at") or _iso(now),
            "phases": [{"name": "rollback", "at": _iso(now)}],
            "failure_reason": None,
            "config_path": (existing or {}).get("config_path") or previous.get("config_path"),
            "runtime_path": previous.get("runtime_path") or (existing or {}).get("runtime_path"),
            "process_identity": previous.get("process_identity"),
            "protected_dirs": (existing or {}).get("protected_dirs") or list(PROTECTED_DIRS),
            "rolled_back_from": (existing or {}).get("version"),
        }
        return self._publish(restored)

    def uninstall(self, now: datetime) -> JournalResult:
        """Mark the install removed. Protected directories are left on disk."""
        _require_aware(now)
        existing, refused = self._existing()
        if refused is not None:
            return refused
        if existing is None or existing.get("phase") == "uninstalled":
            document = {
                "schema_version": SCHEMA_VERSION,
                "phase": "uninstalled",
                "version": None,
                "previous": None,
                "started_at": None,
                "finished_at": _iso(now),
                "phases": [],
                "failure_reason": None,
                "config_path": None,
                "runtime_path": None,
                "process_identity": None,
                "protected_dirs": list((existing or {}).get("protected_dirs") or PROTECTED_DIRS),
            }
            if existing and existing.get("phase") == "uninstalled":
                return JournalResult(True, None, existing)
            return self._publish(document)
        updated = dict(existing)
        updated["phase"] = "uninstalled"
        updated["finished_at"] = _iso(now)
        updated["process_identity"] = None
        return self._publish(updated)

    def _existing(self) -> tuple[dict | None, JournalResult | None]:
        try:
            return self.load(), None
        except JournalUnreadable:
            return None, JournalResult(False, JOURNAL_UNREADABLE, None)

    def _publish(self, document: dict) -> JournalResult:
        try:
            reject_secrets(document)
        except SecretRejected:
            cleaned = scrub_secrets(document)
            try:
                reject_secrets(cleaned)
            except SecretRejected:
                return JournalResult(False, SECRET_REJECTED, self._peek())
            document = cleaned
        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(document, sort_keys=True, indent=2)
        fd, tmp_name = tempfile.mkstemp(prefix=JOURNAL_NAME + ".", suffix=".tmp", dir=self.state_dir)
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self.path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
        return JournalResult(True, None, document)

    def _peek(self) -> dict | None:
        try:
            return self.load()
        except JournalUnreadable:
            return None


def _read_capped(path: Path, cap: int = MAX_STATE_BYTES) -> bytes:
    """Read a state file only when os.stat says it fits, and never more than cap+1 bytes."""
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise JournalUnreadable("unreadable") from exc
    if isinstance(size, bool) or not isinstance(size, int) or size < 0 or size > cap:
        raise JournalUnreadable("unreadable")
    try:
        with path.open("rb") as handle:
            raw = handle.read(cap + 1)
    except OSError as exc:
        raise JournalUnreadable("unreadable") from exc
    if len(raw) > cap:
        raise JournalUnreadable("unreadable")
    return raw


def _status(state: str, now: datetime, *, version, reason_code, worker_id) -> dict[str, Any]:
    if state not in STATES:
        raise ValueError(state)
    if worker_id is not None:
        worker_id = scrub_secrets(worker_id)
        if worker_id == REDACTED:
            worker_id = None
    return {
        "schema_version": SCHEMA_VERSION,
        "state": state,
        "version": version,
        "reason_code": reason_code,
        "checked_at": _iso(now),
        "worker_id": worker_id,
    }


def _completed_gap(journal: Mapping[str, Any], evidence: Evidence, now: datetime, freshness_s: float) -> str | None:
    if not evidence.config_present or not journal.get("config_path"):
        return "MISSING_CONFIG"
    if not evidence.runtime_present or not journal.get("runtime_path"):
        return "MISSING_RUNTIME"
    principal = (evidence.scheduler_principal or "").strip()
    current = (evidence.current_user or "").strip()
    if not evidence.scheduler_registered or not principal or not current or principal != current:
        if principal.lower() in PRIVILEGED_PRINCIPALS:
            return "SCHEDULER_PRIVILEGED_PRINCIPAL"
        return "SCHEDULER_UNREGISTERED"
    if principal.lower() in PRIVILEGED_PRINCIPALS:
        return "SCHEDULER_PRIVILEGED_PRINCIPAL"
    if not evidence.process_alive:
        return "PROCESS_NOT_ALIVE"
    if not _same_identity(journal.get("process_identity"), evidence.process_identity):
        return "PROCESS_IDENTITY_MISMATCH"
    confirmed = evidence.controller_confirmed_at
    finished = _parse_time(journal.get("finished_at"))
    if not evidence.controller_worker_id or confirmed is None or finished is None:
        return CONTROLLER_UNCONFIRMED
    _require_aware(confirmed)
    if confirmed <= finished or confirmed > now or (now - confirmed) > timedelta(seconds=freshness_s):
        return CONTROLLER_STALE
    return None


def _previous_marker(existing: dict | None, version: str) -> dict | None:
    if not existing or existing.get("phase") != "complete":
        return (existing or {}).get("previous") if existing else None
    if existing.get("version") == version:
        return existing.get("previous")
    return {
        "version": existing.get("version"),
        "config_path": existing.get("config_path"),
        "runtime_path": existing.get("runtime_path"),
        "started_at": existing.get("started_at"),
        "finished_at": existing.get("finished_at"),
        "process_identity": existing.get("process_identity"),
    }


def _worker_attributable(existing: dict | None, running_worker: Mapping[str, Any] | None) -> bool:
    if not running_worker or not running_worker.get("alive"):
        return True
    return _same_identity((existing or {}).get("process_identity"), running_worker)


def _same_identity(recorded: Mapping[str, Any] | None, observed: Mapping[str, Any] | None) -> bool:
    if not isinstance(recorded, Mapping) or not isinstance(observed, Mapping):
        return False
    try:
        left = _identity(recorded)
        right = _identity(observed)
    except ValueError:
        return False
    return left == right


def _identity(raw: Mapping[str, Any]) -> dict[str, Any]:
    pid = raw.get("pid")
    start = raw.get("start_time")
    executable = raw.get("executable")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise ValueError("process identity pid must be a positive int")
    if not isinstance(start, str) or not start:
        raise ValueError("process identity start_time is required")
    if not isinstance(executable, str) or not executable:
        raise ValueError("process identity executable is required")
    return {"pid": pid, "start_time": start, "executable": _norm_exe(executable)}


def _norm_exe(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def _protected(given, existing: dict | None) -> list[str]:
    source = list(given) if given is not None else list((existing or {}).get("protected_dirs") or PROTECTED_DIRS)
    names = []
    for name in source:
        if not isinstance(name, str) or not name or name in (".", "..") or "/" in name or "\\" in name:
            raise ValueError("protected directory names must be single path segments")
        if name not in names:
            names.append(name)
    return names


def _key_forbidden(key: str) -> bool:
    parts = [part for part in re.split(r"[^a-z0-9]+", key.lower()) if part]
    flat = "".join(parts)
    if "apikey" in flat:
        return True
    return any(part in _FORBIDDEN_PARTS for part in parts)


def _has_secret(document: Any) -> bool:
    if isinstance(document, Mapping):
        for key, value in document.items():
            if _key_forbidden(str(key)):
                if value != REDACTED:
                    return True
            elif _has_secret(value):
                return True
        return False
    if isinstance(document, list):
        return any(_has_secret(item) for item in document)
    return isinstance(document, str) and _BEARER.search(document) is not None


def _require_version(version: str) -> None:
    if not isinstance(version, str) or not version.strip():
        raise ValueError("version is required")


def _require_aware(moment: datetime) -> None:
    if not isinstance(moment, datetime) or moment.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)
