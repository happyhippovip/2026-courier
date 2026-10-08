"""Gate production work on a passed qualification probe set.

A provider is identified by its provider identity: name (``provider_id``),
version, and config hash (the identity fingerprint). The caller supplies
the probes. Each probe returns pass or fail plus a short evidence string.
Results are stored in one JSON document. A missing record, a failed probe,
a stale record, or a malformed store means the provider is not qualified.
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

STATUS_QUALIFIED = "QUALIFIED"
STATUS_UNQUALIFIED = "UNQUALIFIED"
STATUS_STALE = "STALE"
_STATUSES = frozenset({STATUS_QUALIFIED, STATUS_UNQUALIFIED, STATUS_STALE})

MAX_STORE_BYTES = 1024 * 1024
_MAX_PROBES = 32
_MAX_PROBE_ID = 200
_MAX_EVIDENCE = 1024
_MAX_NAME = 200
_RECORD_FIELDS = (
    "name",
    "version",
    "config_hash",
    "probe_results",
    "recorded_at",
    "status",
)
_PROBE_FIELDS = ("probe_id", "passed", "evidence")
_STORE_FIELDS = ("records",)

_thread_locks_guard = threading.Lock()
_thread_locks: dict[str, threading.Lock] = {}


class QualificationError(ValueError):
    """The store or a record is missing a field, has an unknown field, or is malformed."""


@dataclass(frozen=True)
class ProbeResult:
    probe_id: str
    passed: bool
    evidence: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "probe_id", _probe_id(self.probe_id))
        if not isinstance(self.passed, bool):
            raise QualificationError("passed must be a boolean")
        object.__setattr__(self, "evidence", _evidence(self.evidence))

    def to_dict(self) -> dict:
        return {
            "probe_id": self.probe_id,
            "passed": self.passed,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, data: object) -> "ProbeResult":
        if not isinstance(data, dict):
            raise QualificationError("probe result must be an object")
        _require_exact_keys(data, _PROBE_FIELDS, "probe result")
        return cls(
            probe_id=data["probe_id"],
            passed=data["passed"],
            evidence=data["evidence"],
        )


@dataclass(frozen=True)
class QualificationRecord:
    name: str
    version: str
    config_hash: str
    probe_results: tuple[ProbeResult, ...]
    recorded_at: str
    status: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _name(self.name))
        if not isinstance(self.version, str) or not self.version.strip() or len(self.version) > 4096:
            raise QualificationError("version must be a bounded string")
        object.__setattr__(self, "version", self.version.strip())
        if not _is_sha256(self.config_hash):
            raise QualificationError("config_hash must be a sha256 hex digest")
        if not isinstance(self.probe_results, tuple):
            raise QualificationError("probe_results must be a tuple")
        if len(self.probe_results) > _MAX_PROBES:
            raise QualificationError("too many probe results")
        for item in self.probe_results:
            if not isinstance(item, ProbeResult):
                raise QualificationError("probe_results must contain probe results")
        if not _is_iso_z(self.recorded_at):
            raise QualificationError("recorded_at must be an ISO timestamp ending in Z")
        if self.status not in _STATUSES:
            raise QualificationError("status is not a known value")
        if self.status == STATUS_QUALIFIED and not _all_passed(self.probe_results):
            raise QualificationError("a qualified record requires every probe to pass")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "config_hash": self.config_hash,
            "probe_results": [item.to_dict() for item in self.probe_results],
            "recorded_at": self.recorded_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: object) -> "QualificationRecord":
        if not isinstance(data, dict):
            raise QualificationError("record must be an object")
        _require_exact_keys(data, _RECORD_FIELDS, "record")
        probes = data["probe_results"]
        if not isinstance(probes, list):
            raise QualificationError("probe_results must be a list")
        return cls(
            name=data["name"],
            version=data["version"],
            config_hash=data["config_hash"],
            probe_results=tuple(ProbeResult.from_dict(item) for item in probes),
            recorded_at=data["recorded_at"],
            status=data["status"],
        )


class QualificationStore:
    """Atomic JSON store of qualification records.

    Reads fail closed: a missing file has no qualified providers, and a
    malformed file is not qualified. ``mark_stale`` is the hook a separate
    invalidation module calls.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def is_qualified(self, identity: ProviderIdentity) -> bool:
        """Return whether this identity has a current QUALIFIED record."""
        if not isinstance(identity, ProviderIdentity):
            return False
        try:
            records = self._read()
        except QualificationError:
            return False
        return _matches_qualified(records, identity)

    def mark_stale(self, predicate) -> int:
        """Set status to STALE where ``predicate(record)`` is true.

        Returns how many records changed. A malformed store raises and is
        left unchanged.
        """
        if not callable(predicate):
            raise QualificationError("predicate must be callable")
        with _locked(self.path):
            records = self._load()
            if records is None:
                return 0
            changed = 0
            updated: list[QualificationRecord] = []
            for record in records:
                if predicate(record) and record.status != STATUS_STALE:
                    record = QualificationRecord(
                        name=record.name,
                        version=record.version,
                        config_hash=record.config_hash,
                        probe_results=record.probe_results,
                        recorded_at=record.recorded_at,
                        status=STATUS_STALE,
                    )
                    changed += 1
                updated.append(record)
            if changed:
                self._write(updated)
            return changed

    def put(self, record: QualificationRecord) -> None:
        if not isinstance(record, QualificationRecord):
            raise QualificationError("record must be a qualification record")
        with _locked(self.path):
            current = self._load()
            if current is None:
                current = []
            merged = [item for item in current if item.config_hash != record.config_hash]
            merged.append(record)
            self._write(merged)

    def read(self) -> tuple[QualificationRecord, ...]:
        """Return the stored records. A malformed store raises."""
        with _locked(self.path):
            loaded = self._load()
        return tuple(loaded or ())

    def _read(self) -> tuple[QualificationRecord, ...]:
        with _locked(self.path):
            loaded = self._load()
        return tuple(loaded or ())

    def _load(self) -> list[QualificationRecord] | None:
        if not self.path.exists():
            return None
        try:
            size = self.path.stat().st_size
        except OSError as exc:
            raise QualificationError("store could not be read") from exc
        if size > MAX_STORE_BYTES:
            raise QualificationError("store exceeds 1 MiB")
        try:
            raw = self.path.read_bytes()
        except OSError as exc:
            raise QualificationError("store could not be read") from exc
        if len(raw) > MAX_STORE_BYTES:
            raise QualificationError("store exceeds 1 MiB")
        try:
            text = raw.decode("utf-8")
            data = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise QualificationError("store is malformed") from exc
        if not isinstance(data, dict):
            raise QualificationError("store must be an object")
        _require_exact_keys(data, _STORE_FIELDS, "store")
        rows = data["records"]
        if not isinstance(rows, list):
            raise QualificationError("records must be a list")
        records = [QualificationRecord.from_dict(item) for item in rows]
        seen: set[str] = set()
        for record in records:
            if record.config_hash in seen:
                raise QualificationError("duplicate config_hash")
            seen.add(record.config_hash)
        return records

    def _write(self, records: list[QualificationRecord]) -> None:
        payload = {
            "records": [record.to_dict() for record in sorted(records, key=lambda item: item.config_hash)],
        }
        encoded = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True).encode("utf-8") + b"\n"
        if len(encoded) > MAX_STORE_BYTES:
            raise QualificationError("store exceeds 1 MiB")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(
            f".{self.path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        try:
            tmp.write_bytes(encoded)
            os.replace(tmp, self.path)
        finally:
            if tmp.exists():
                tmp.unlink()


def is_qualified(identity: ProviderIdentity, store: QualificationStore) -> bool:
    """Return whether ``identity`` may receive production work."""
    if not isinstance(store, QualificationStore):
        return False
    return store.is_qualified(identity)


def qualify(
    identity: ProviderIdentity,
    probes,
    store: QualificationStore,
    *,
    at: str | None = None,
) -> QualificationRecord:
    """Run ``probes`` and persist QUALIFIED or UNQUALIFIED for this identity.

    A probe is an object with ``probe_id`` and ``run(identity) -> ProbeResult``.
    An empty probe list, a failed probe, or a probe that does not finish is
    stored as UNQUALIFIED.
    """
    if not isinstance(identity, ProviderIdentity):
        raise QualificationError("identity must be a provider identity")
    if not isinstance(store, QualificationStore):
        raise QualificationError("store must be a qualification store")
    if isinstance(probes, (str, bytes)) or not isinstance(probes, (list, tuple)):
        raise QualificationError("probes must be a list")
    if len(probes) > _MAX_PROBES:
        raise QualificationError("too many probes")
    stamp = at or _now_z()
    if not _is_iso_z(stamp):
        raise QualificationError("timestamp must be an ISO timestamp ending in Z")
    results = _run_probes(identity, probes)
    status = STATUS_QUALIFIED if results and all(item.passed for item in results) else STATUS_UNQUALIFIED
    record = QualificationRecord(
        name=identity.provider_id,
        version=identity.version,
        config_hash=identity.fingerprint(),
        probe_results=tuple(results),
        recorded_at=stamp,
        status=status,
    )
    store.put(record)
    return record


def _run_probes(identity: ProviderIdentity, probes) -> list[ProbeResult]:
    results: list[ProbeResult] = []
    seen: set[str] = set()
    for probe in probes:
        result = _execute_probe(probe, identity)
        if result.probe_id in seen:
            result = ProbeResult(result.probe_id, False, "duplicate probe id")
        seen.add(result.probe_id)
        results.append(result)
    return results


def _execute_probe(probe: object, identity: ProviderIdentity) -> ProbeResult:
    probe_id = getattr(probe, "probe_id", None)
    if not isinstance(probe_id, str):
        return ProbeResult("unknown", False, "probe id is missing")
    try:
        cleaned = _probe_id(probe_id)
    except QualificationError:
        return ProbeResult("unknown", False, "probe id is missing")
    run = getattr(probe, "run", None)
    if not callable(run):
        return ProbeResult(cleaned, False, "probe has no run method")
    try:
        result = run(identity)
    except Exception:
        return ProbeResult(cleaned, False, "probe failed to finish")
    if not isinstance(result, ProbeResult) or result.probe_id != cleaned:
        return ProbeResult(cleaned, False, "probe returned an unrecognized result")
    return result


def _all_passed(results: tuple[ProbeResult, ...]) -> bool:
    return bool(results) and all(item.passed for item in results)


def _matches_qualified(records: tuple[QualificationRecord, ...], identity: ProviderIdentity) -> bool:
    want = identity.fingerprint()
    matched = [record for record in records if record.config_hash == want]
    if len(matched) != 1:
        return False
    record = matched[0]
    return (
        record.status == STATUS_QUALIFIED
        and record.name == identity.provider_id
        and record.version == identity.version
        and record.config_hash == want
    )


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
        lock_path = path.with_name(path.name + ".lock")
        handle = open(lock_path, "a+b")
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


def _require_exact_keys(data: dict, fields: tuple[str, ...], label: str) -> None:
    unknown = sorted(set(data) - set(fields))
    missing = [name for name in fields if name not in data]
    if unknown:
        raise QualificationError(f"unknown field: {', '.join(unknown)}")
    if missing:
        raise QualificationError(f"missing field: {', '.join(missing)}")


def _probe_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > _MAX_PROBE_ID
        or any(ch in value for ch in "\n\r\x00")
    ):
        raise QualificationError("probe id must be a single line")
    return value.strip()


def _name(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > _MAX_NAME
        or any(ch in value for ch in "\n\r\x00")
    ):
        raise QualificationError("name must be a single line")
    return value.strip()


def _evidence(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > _MAX_EVIDENCE or "\x00" in value:
        raise QualificationError("evidence must be a bounded string")
    return value.strip()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


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
