"""Track whether a provider may return to rotation.

A provider that was gone and comes back is STALE. STALE and QUARANTINED
providers stay out of rotation. A requalification probe is a harmless
idempotent task plus a verifier result. An accepted probe moves STALE or
QUARANTINED to STANDBY, and STANDBY to ACTIVE. Two failed probes move the
provider to QUARANTINED. Nothing in this module rebinds a provider without
an accepted probe.
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

STATUS_ACTIVE = "ACTIVE"
STATUS_STANDBY = "STANDBY"
STATUS_STALE = "STALE"
STATUS_QUARANTINED = "QUARANTINED"
_STATUSES = frozenset({STATUS_ACTIVE, STATUS_STANDBY, STATUS_STALE, STATUS_QUARANTINED})
_ROTATION = frozenset({STATUS_ACTIVE, STATUS_STANDBY})

MAX_STORE_BYTES = 1024 * 1024
_RECORD_FIELDS = (
    "provider_id",
    "status",
    "departed",
    "probe_failures",
    "last_probe_id",
    "updated_at",
)
_STORE_FIELDS = ("providers",)

_thread_locks_guard = threading.Lock()
_thread_locks: dict[str, threading.Lock] = {}


class RegistryError(ValueError):
    """The registry is malformed, or the provider or probe cannot be applied."""


@dataclass(frozen=True)
class ProbeTask:
    task_id: str
    idempotent: bool
    harmless: bool
    verifier_accepted: bool

    def __post_init__(self) -> None:
        if (
            not isinstance(self.task_id, str)
            or not self.task_id.strip()
            or len(self.task_id.strip()) > 200
            or any(ch in self.task_id for ch in "\n\r\x00/\\")
        ):
            raise RegistryError("task id must be a single token")
        object.__setattr__(self, "task_id", self.task_id.strip())
        if not isinstance(self.idempotent, bool) or not isinstance(self.harmless, bool):
            raise RegistryError("probe flags must be booleans")
        if not isinstance(self.verifier_accepted, bool):
            raise RegistryError("verifier result must be a boolean")
        if not self.idempotent or not self.harmless:
            raise RegistryError("probe must be a harmless idempotent task")


@dataclass(frozen=True)
class ProviderPresence:
    provider_id: str
    status: str
    departed: bool
    probe_failures: int
    last_probe_id: str | None
    updated_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _provider_id(self.provider_id))
        if self.status not in _STATUSES:
            raise RegistryError("status is not a known value")
        if not isinstance(self.departed, bool):
            raise RegistryError("departed must be a boolean")
        if isinstance(self.probe_failures, bool) or not isinstance(self.probe_failures, int) or self.probe_failures < 0:
            raise RegistryError("probe_failures must be a non-negative integer")
        if self.last_probe_id is not None:
            object.__setattr__(self, "last_probe_id", _token(self.last_probe_id, "last_probe_id"))
        if not _is_iso_z(self.updated_at):
            raise RegistryError("updated_at must be an ISO timestamp ending in Z")

    def to_dict(self) -> dict:
        return {
            "provider_id": self.provider_id,
            "status": self.status,
            "departed": self.departed,
            "probe_failures": self.probe_failures,
            "last_probe_id": self.last_probe_id,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: object) -> "ProviderPresence":
        if not isinstance(data, dict):
            raise RegistryError("provider must be an object")
        _require_exact_keys(data, _RECORD_FIELDS, "provider")
        return cls(
            provider_id=data["provider_id"],
            status=data["status"],
            departed=data["departed"],
            probe_failures=data["probe_failures"],
            last_probe_id=data["last_probe_id"],
            updated_at=data["updated_at"],
        )


class ProviderRegistry:
    """Atomic JSON registry. A malformed file raises. A missing provider is unknown."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def register(self, provider_id: str, *, at: str | None = None) -> ProviderPresence:
        """Record a provider as STANDBY. A second call returns the existing row."""
        stamp = _stamp(at)
        name = _provider_id(provider_id)
        with _locked(self.path):
            rows = self._load() or []
            current = _find(rows, name)
            if current is not None:
                return current
            created = ProviderPresence(name, STATUS_STANDBY, False, 0, None, stamp)
            rows.append(created)
            self._write(rows)
            return created

    def note_departure(self, provider_id: str, *, at: str | None = None) -> ProviderPresence:
        stamp = _stamp(at)
        with _locked(self.path):
            rows = self._require_rows()
            current = _require_provider(rows, provider_id)
            if current.departed:
                return current
            updated = _replace(current, departed=True, updated_at=stamp)
            self._write(_replace_row(rows, updated))
            return updated

    def note_return(self, provider_id: str, *, at: str | None = None) -> ProviderPresence:
        """A departed provider comes back as STALE. This does not rebind it."""
        stamp = _stamp(at)
        with _locked(self.path):
            rows = self._require_rows()
            current = _require_provider(rows, provider_id)
            if not current.departed:
                return current
            updated = ProviderPresence(
                provider_id=current.provider_id,
                status=STATUS_STALE,
                departed=False,
                probe_failures=0,
                last_probe_id=None,
                updated_at=stamp,
            )
            self._write(_replace_row(rows, updated))
            return updated

    def apply_probe(self, provider_id: str, probe: ProbeTask, *, at: str | None = None) -> ProviderPresence:
        """Apply one verifier result. Replaying the same task id changes nothing."""
        if not isinstance(probe, ProbeTask):
            raise RegistryError("probe must be a probe task")
        stamp = _stamp(at)
        with _locked(self.path):
            rows = self._require_rows()
            current = _require_provider(rows, provider_id)
            if current.last_probe_id == probe.task_id:
                return current
            updated = _after_probe(current, probe, stamp)
            self._write(_replace_row(rows, updated))
            return updated

    def status_of(self, provider_id: str) -> str | None:
        name = _provider_id(provider_id)
        for record in self.read():
            if record.provider_id == name:
                return record.status
        return None

    def in_rotation(self, provider_id: str) -> bool:
        return self.status_of(provider_id) in _ROTATION

    def read(self) -> tuple[ProviderPresence, ...]:
        with _locked(self.path):
            loaded = self._load()
        return tuple(sorted(loaded or [], key=lambda item: item.provider_id))

    def _require_rows(self) -> list[ProviderPresence]:
        loaded = self._load()
        if loaded is None:
            raise RegistryError("unknown provider")
        return loaded

    def _load(self) -> list[ProviderPresence] | None:
        if not self.path.exists():
            return None
        try:
            raw = self.path.read_bytes()
        except OSError as exc:
            raise RegistryError("registry could not be read") from exc
        if len(raw) > MAX_STORE_BYTES:
            raise RegistryError("registry exceeds 1 MiB")
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RegistryError("registry is malformed") from exc
        if not isinstance(data, dict):
            raise RegistryError("registry must be an object")
        _require_exact_keys(data, _STORE_FIELDS, "registry")
        rows = data["providers"]
        if not isinstance(rows, list):
            raise RegistryError("providers must be a list")
        records = [ProviderPresence.from_dict(item) for item in rows]
        seen: set[str] = set()
        for record in records:
            if record.provider_id in seen:
                raise RegistryError("duplicate provider")
            seen.add(record.provider_id)
        return records

    def _write(self, rows: list[ProviderPresence]) -> None:
        payload = {
            "providers": [record.to_dict() for record in sorted(rows, key=lambda item: item.provider_id)],
        }
        encoded = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True).encode("utf-8") + b"\n"
        if len(encoded) > MAX_STORE_BYTES:
            raise RegistryError("registry exceeds 1 MiB")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f".{self.path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            tmp.write_bytes(encoded)
            os.replace(tmp, self.path)
        finally:
            if tmp.exists():
                tmp.unlink()


def _after_probe(current: ProviderPresence, probe: ProbeTask, stamp: str) -> ProviderPresence:
    if probe.verifier_accepted:
        if current.status in (STATUS_STALE, STATUS_QUARANTINED):
            status = STATUS_STANDBY
        else:
            status = STATUS_ACTIVE
        failures = 0
    else:
        failures = current.probe_failures + 1
        status = STATUS_QUARANTINED if failures >= 2 else current.status
    return ProviderPresence(
        provider_id=current.provider_id,
        status=status,
        departed=current.departed,
        probe_failures=failures,
        last_probe_id=probe.task_id,
        updated_at=stamp,
    )


def _replace(current: ProviderPresence, **changes) -> ProviderPresence:
    data = current.to_dict()
    data.update(changes)
    return ProviderPresence.from_dict(data)


def _find(rows: list[ProviderPresence], provider_id: str) -> ProviderPresence | None:
    name = _provider_id(provider_id)
    for record in rows:
        if record.provider_id == name:
            return record
    return None


def _require_provider(rows: list[ProviderPresence], provider_id: str) -> ProviderPresence:
    found = _find(rows, provider_id)
    if found is None:
        raise RegistryError("unknown provider")
    return found


def _replace_row(rows: list[ProviderPresence], updated: ProviderPresence) -> list[ProviderPresence]:
    return [updated if item.provider_id == updated.provider_id else item for item in rows]


def _stamp(at: str | None) -> str:
    stamp = at or _now_z()
    if not _is_iso_z(stamp):
        raise RegistryError("timestamp must be an ISO timestamp ending in Z")
    return stamp


def _provider_id(value: object) -> str:
    return _token(value, "provider id")


def _token(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > 200
        or any(ch in value for ch in "\n\r\x00/\\")
    ):
        raise RegistryError(f"{label} must be a single token")
    return value.strip()


def _require_exact_keys(data: dict, fields: tuple[str, ...], label: str) -> None:
    unknown = sorted(set(data) - set(fields))
    missing = [name for name in fields if name not in data]
    if unknown:
        raise RegistryError(f"unknown field: {', '.join(unknown)}")
    if missing:
        raise RegistryError(f"missing field: {', '.join(missing)}")


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
            if os.name == "nt":
                import msvcrt

                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"\0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            if os.name == "nt":
                import msvcrt

                try:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()
