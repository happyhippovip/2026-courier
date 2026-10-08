"""Mark qualification records stale when a provider identity changes.

Identity facts that select a qualification are the binary hash, the version,
and the profile flags (provider kind and version source). A change marks
every qualification record bound to the old identity stale through
``QualificationStore.mark_stale``. The stale record does not admit work
until a later qualification. The invalidation log stores the reason and the
old and new identity fingerprints.
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from courier_core.provider_identity import ProviderIdentity
from courier_core.provider_qualification import QualificationRecord, QualificationStore

REASON_VERSION = "version"
REASON_BINARY = "binary"
REASON_PROFILE = "profile"
REASON_IDENTITY = "identity"
_REASONS = frozenset({REASON_VERSION, REASON_BINARY, REASON_PROFILE, REASON_IDENTITY})

MAX_LOG_BYTES = 1024 * 1024
_EVENT_FIELDS = (
    "provider_name",
    "old_fingerprint",
    "new_fingerprint",
    "reason",
    "recorded_at",
)
_LOG_FIELDS = ("events",)

_thread_locks_guard = threading.Lock()
_thread_locks: dict[str, threading.Lock] = {}


class InvalidationError(ValueError):
    """The provider is unknown, the log is malformed, or the change cannot be applied."""


@dataclass(frozen=True)
class InvalidationEvent:
    provider_name: str
    old_fingerprint: str
    new_fingerprint: str
    reason: str
    recorded_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_name", _provider_name(self.provider_name))
        object.__setattr__(self, "old_fingerprint", _fingerprint(self.old_fingerprint, "old_fingerprint"))
        object.__setattr__(self, "new_fingerprint", _fingerprint(self.new_fingerprint, "new_fingerprint"))
        if self.reason not in _REASONS:
            raise InvalidationError("reason is not a known value")
        if not _is_iso_z(self.recorded_at):
            raise InvalidationError("recorded_at must be an ISO timestamp ending in Z")

    def to_dict(self) -> dict:
        return {
            "provider_name": self.provider_name,
            "old_fingerprint": self.old_fingerprint,
            "new_fingerprint": self.new_fingerprint,
            "reason": self.reason,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, data: object) -> "InvalidationEvent":
        if not isinstance(data, dict):
            raise InvalidationError("event must be an object")
        _require_exact_keys(data, _EVENT_FIELDS, "event")
        return cls(
            provider_name=data["provider_name"],
            old_fingerprint=data["old_fingerprint"],
            new_fingerprint=data["new_fingerprint"],
            reason=data["reason"],
            recorded_at=data["recorded_at"],
        )

    def key(self) -> tuple[str, str, str, str]:
        return (self.provider_name, self.old_fingerprint, self.new_fingerprint, self.reason)


@dataclass(frozen=True)
class InvalidationResult:
    old_fingerprint: str
    new_fingerprint: str
    reason: str | None
    marked_stale: int
    records: tuple[QualificationRecord, ...]


class InvalidationLog:
    """Atomic JSON log of invalidation events. A malformed file raises."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def read(self) -> tuple[InvalidationEvent, ...]:
        with _locked(self.path):
            loaded = self._load()
        return tuple(loaded or ())

    def append(self, event: InvalidationEvent) -> bool:
        """Persist ``event`` once. Return False when that event is already stored."""
        if not isinstance(event, InvalidationEvent):
            raise InvalidationError("event must be an invalidation event")
        with _locked(self.path):
            current = self._load()
            if current is None:
                current = []
            if any(item.key() == event.key() for item in current):
                return False
            current.append(event)
            self._write(current)
            return True

    def _load(self) -> list[InvalidationEvent] | None:
        if not self.path.exists():
            return None
        try:
            size = self.path.stat().st_size
        except OSError as exc:
            raise InvalidationError("log could not be read") from exc
        if size > MAX_LOG_BYTES:
            raise InvalidationError("log exceeds 1 MiB")
        try:
            raw = self.path.read_bytes()
        except OSError as exc:
            raise InvalidationError("log could not be read") from exc
        if len(raw) > MAX_LOG_BYTES:
            raise InvalidationError("log exceeds 1 MiB")
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidationError("log is malformed") from exc
        if not isinstance(data, dict):
            raise InvalidationError("log must be an object")
        _require_exact_keys(data, _LOG_FIELDS, "log")
        rows = data["events"]
        if not isinstance(rows, list):
            raise InvalidationError("events must be a list")
        events = [InvalidationEvent.from_dict(item) for item in rows]
        seen: set[tuple[str, str, str, str]] = set()
        for event in events:
            if event.key() in seen:
                raise InvalidationError("duplicate event")
            seen.add(event.key())
        return events

    def _write(self, events: list[InvalidationEvent]) -> None:
        payload = {"events": [event.to_dict() for event in events]}
        encoded = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True).encode("utf-8") + b"\n"
        if len(encoded) > MAX_LOG_BYTES:
            raise InvalidationError("log exceeds 1 MiB")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f".{self.path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            tmp.write_bytes(encoded)
            os.replace(tmp, self.path)
        finally:
            if tmp.exists():
                tmp.unlink()


def profile_flags(identity: ProviderIdentity) -> tuple[str, str]:
    """Return provider kind and version source.

    These are the profile flags carried on the provider identity. Version
    and binary hash are not profile flags.
    """
    _require_identity(identity)
    return (identity.provider_kind, identity.version_source)


def change_reason(old: ProviderIdentity, new: ProviderIdentity) -> str | None:
    """Return why ``new`` differs from ``old``, or None when the fingerprint matches."""
    _require_pair(old, new)
    if old.fingerprint() == new.fingerprint():
        return None
    changed = []
    if old.version != new.version:
        changed.append(REASON_VERSION)
    if old.binary_fingerprint != new.binary_fingerprint:
        changed.append(REASON_BINARY)
    if profile_flags(old) != profile_flags(new):
        changed.append(REASON_PROFILE)
    if len(changed) == 1:
        return changed[0]
    if not changed:
        raise InvalidationError("identity fingerprint changed without a known fact")
    return REASON_IDENTITY


def invalidated_records(
    records: tuple[QualificationRecord, ...] | list[QualificationRecord],
    old: ProviderIdentity,
    new: ProviderIdentity,
) -> tuple[QualificationRecord, ...]:
    """Return qualification records bound to ``old`` when the identity changed.

    This function does not read or write a store. An unchanged fingerprint
    selects nothing. Records are bound by provider name and the old identity
    fingerprint.
    """
    _require_pair(old, new)
    if isinstance(records, (str, bytes)) or not isinstance(records, (tuple, list)):
        raise InvalidationError("records must be a sequence")
    for record in records:
        if not isinstance(record, QualificationRecord):
            raise InvalidationError("records must contain qualification records")
    if old.fingerprint() == new.fingerprint():
        return ()
    old_hash = old.fingerprint()
    return tuple(
        record
        for record in records
        if record.name == old.provider_id and record.config_hash == old_hash
    )


def invalidate(
    old: ProviderIdentity,
    new: ProviderIdentity,
    store: QualificationStore,
    log: InvalidationLog,
    *,
    at: str | None = None,
) -> InvalidationResult:
    """Mark qualifications bound to ``old`` stale and persist one event.

    A second call with the same identities does not add another event and
    does not change records that are already stale. An unknown provider
    raises and leaves every store unchanged.
    """
    _require_pair(old, new)
    if not isinstance(store, QualificationStore):
        raise InvalidationError("store must be a qualification store")
    if not isinstance(log, InvalidationLog):
        raise InvalidationError("log must be an invalidation log")
    stamp = at or _now_z()
    if not _is_iso_z(stamp):
        raise InvalidationError("timestamp must be an ISO timestamp ending in Z")
    records = store.read()
    _require_known_provider(records, old)
    selected = invalidated_records(records, old, new)
    reason = change_reason(old, new)
    if reason is None:
        return InvalidationResult(
            old_fingerprint=old.fingerprint(),
            new_fingerprint=new.fingerprint(),
            reason=None,
            marked_stale=0,
            records=(),
        )
    if not selected:
        raise InvalidationError("old identity is not bound")
    # Read the log before mutation so a malformed log does not leave a partial update.
    log.read()
    marked = store.mark_stale(_bound_to(old))
    event = InvalidationEvent(
        provider_name=old.provider_id,
        old_fingerprint=old.fingerprint(),
        new_fingerprint=new.fingerprint(),
        reason=reason,
        recorded_at=stamp,
    )
    log.append(event)
    return InvalidationResult(
        old_fingerprint=old.fingerprint(),
        new_fingerprint=new.fingerprint(),
        reason=reason,
        marked_stale=marked,
        records=selected,
    )


def _bound_to(old: ProviderIdentity):
    old_hash = old.fingerprint()
    name = old.provider_id

    def predicate(record: QualificationRecord) -> bool:
        return record.name == name and record.config_hash == old_hash

    return predicate


def _require_known_provider(records: tuple[QualificationRecord, ...], old: ProviderIdentity) -> None:
    if not any(record.name == old.provider_id for record in records):
        raise InvalidationError("unknown provider")


def _require_pair(old: object, new: object) -> None:
    _require_identity(old)
    _require_identity(new)
    if old.provider_id != new.provider_id:
        raise InvalidationError("provider name does not match")


def _require_identity(identity: object) -> None:
    if not isinstance(identity, ProviderIdentity):
        raise InvalidationError("identity must be a provider identity")


def _provider_name(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > 200
        or any(ch in value for ch in "\n\r\x00/\\")
    ):
        raise InvalidationError("provider name must be a single token")
    return value.strip()


def _fingerprint(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise InvalidationError(f"{label} must be a sha256 hex digest")
    return value


def _require_exact_keys(data: dict, fields: tuple[str, ...], label: str) -> None:
    unknown = sorted(set(data) - set(fields))
    missing = [name for name in fields if name not in data]
    if unknown:
        raise InvalidationError(f"unknown field: {', '.join(unknown)}")
    if missing:
        raise InvalidationError(f"missing field: {', '.join(missing)}")


def _is_iso_z(value: object) -> bool:
    if not isinstance(value, str) or len(value) < 20 or not value.endswith("Z"):
        return False
    body = value[:-1]
    if "." in body:
        head, frac = body.split(".", 1)
        if not frac.isdigit() or not 1 <= len(frac) <= 6:
            return False
    else:
        head = body
    try:
        datetime.strptime(head, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return False
    return True


def _now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextmanager
def _locked(path: Path):
    key = str(path)
    with _thread_locks_guard:
        lock = _thread_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _thread_locks[key] = lock
    with lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(path.with_name(path.name + ".lock"), "a+b")
        try:
            _file_lock(handle)
            yield
        finally:
            _file_unlock(handle)
            handle.close()


def _file_lock(handle) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _file_unlock(handle) -> None:
    if os.name == "nt":
        import msvcrt

        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            return
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
