"""Record which provider and version produced a result.

``capture_identity`` runs a version command without a shell. A timeout, a
nonzero exit, or any execution error is stored as version ``UNKNOWN``.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_CAP = 4096
VERSION_UNKNOWN = "UNKNOWN"
SOURCE_CLI = "cli_reported"
SOURCE_CONFIG = "config"
SOURCE_UNKNOWN = "unknown"
_SOURCES = frozenset({SOURCE_CLI, SOURCE_CONFIG, SOURCE_UNKNOWN})
_FIELDS = (
    "provider_id",
    "provider_kind",
    "version",
    "version_source",
    "binary_fingerprint",
    "captured_at",
)
_MAX_TEXT = 200
_ISO_Z_MIN = 20  # YYYY-MM-DDTHH:MM:SSZ


class ProviderIdentityError(ValueError):
    """The record is missing a field, has an unknown field, or is malformed."""


@dataclass(frozen=True)
class ProviderIdentity:
    provider_id: str
    provider_kind: str
    version: str
    version_source: str
    binary_fingerprint: str | None
    captured_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _token(self.provider_id, "provider_id"))
        object.__setattr__(self, "provider_kind", _token(self.provider_kind, "provider_kind"))
        if not isinstance(self.version, str) or not self.version.strip() or len(self.version) > OUTPUT_CAP or "\n" in self.version or "\r" in self.version:
            raise ProviderIdentityError("version must be a single bounded line")
        object.__setattr__(self, "version", self.version.strip())
        if self.version_source not in _SOURCES:
            raise ProviderIdentityError("version_source is not a known value")
        if self.version_source == SOURCE_UNKNOWN and self.version != VERSION_UNKNOWN:
            raise ProviderIdentityError("an unknown source must record version UNKNOWN")
        if self.binary_fingerprint is not None and not _is_sha256(self.binary_fingerprint):
            raise ProviderIdentityError("binary_fingerprint must be a sha256 hex digest or null")
        if not _is_iso_z(self.captured_at):
            raise ProviderIdentityError("captured_at must be an ISO timestamp ending in Z")

    def fingerprint(self) -> str:
        """Stable digest of provider, version, source, and binary facts.

        The capture time is not included, so two captures of the same binary
        and version compare equal.
        """
        body = {
            "binary_fingerprint": self.binary_fingerprint,
            "provider_id": self.provider_id,
            "provider_kind": self.provider_kind,
            "version": self.version,
            "version_source": self.version_source,
        }
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return {
            "provider_id": self.provider_id,
            "provider_kind": self.provider_kind,
            "version": self.version,
            "version_source": self.version_source,
            "binary_fingerprint": self.binary_fingerprint,
            "captured_at": self.captured_at,
        }

    @classmethod
    def from_dict(cls, data: object) -> "ProviderIdentity":
        if not isinstance(data, dict):
            raise ProviderIdentityError("record must be an object")
        unknown = sorted(set(data) - set(_FIELDS))
        missing = [name for name in _FIELDS if name not in data]
        if unknown:
            raise ProviderIdentityError(f"unknown field: {', '.join(unknown)}")
        if missing:
            raise ProviderIdentityError(f"missing field: {', '.join(missing)}")
        return cls(
            provider_id=data["provider_id"],
            provider_kind=data["provider_kind"],
            version=data["version"],
            version_source=data["version_source"],
            binary_fingerprint=data["binary_fingerprint"],
            captured_at=data["captured_at"],
        )


def capture_identity(
    provider_id: str,
    argv_version_cmd: list | tuple,
    timeout: float,
    *,
    provider_kind: str,
    captured_at: str | None = None,
) -> ProviderIdentity:
    """Run ``argv_version_cmd`` without a shell and record the reported version.

    ``timeout`` is seconds. Stdout is kept up to ``OUTPUT_CAP`` bytes. Timeout,
    nonzero exit, and any execution error become version ``UNKNOWN``.
    """
    stamp = captured_at or _now_z()
    kind = provider_kind
    binary = _binary_fingerprint(_argv0(argv_version_cmd))
    try:
        version = _run_version(argv_version_cmd, timeout)
    except (OSError, ValueError, subprocess.SubprocessError):
        version = None
    if version:
        return ProviderIdentity(
            provider_id=provider_id,
            provider_kind=kind,
            version=version,
            version_source=SOURCE_CLI,
            binary_fingerprint=binary,
            captured_at=stamp,
        )
    return ProviderIdentity(
        provider_id=provider_id,
        provider_kind=kind,
        version=VERSION_UNKNOWN,
        version_source=SOURCE_UNKNOWN,
        binary_fingerprint=binary,
        captured_at=stamp,
    )


def _run_version(argv: list | tuple, timeout: float) -> str | None:
    if isinstance(argv, (str, bytes)) or not isinstance(argv, (list, tuple)):
        raise ValueError("argv must be a list of arguments")
    if not argv or any(not isinstance(part, str) or not part for part in argv):
        raise ValueError("argv must be a non-empty list of strings")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 60:
        raise ValueError("timeout must be a positive number of seconds up to 60")
    proc = subprocess.Popen(
        list(argv),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        shell=False,
        start_new_session=(os.name != "nt"),
    )
    try:
        stdout, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _stop(proc)
        return None
    if proc.returncode != 0:
        return None
    text = stdout[:OUTPUT_CAP].decode("utf-8", errors="replace")
    line = text.split("\n", 1)[0].strip("\r").strip()
    if not line:
        return None
    return line[:OUTPUT_CAP]


def _stop(proc: subprocess.Popen) -> None:
    if os.name != "nt":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
    else:
        proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _argv0(argv: list | tuple) -> str | None:
    if isinstance(argv, (str, bytes)) or not isinstance(argv, (list, tuple)) or not argv:
        return None
    first = argv[0]
    if not isinstance(first, str) or not first:
        return None
    return first


def _binary_fingerprint(argv0: str | None) -> str | None:
    if not argv0:
        return None
    resolved = _resolve_binary(argv0)
    if resolved is None:
        return None
    try:
        stat = resolved.stat()
    except OSError:
        return None
    material = f"{resolved}\n{stat.st_size}\n{stat.st_mtime_ns}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _resolve_binary(argv0: str) -> Path | None:
    candidate = Path(argv0)
    if candidate.is_file():
        return candidate.resolve()
    found = shutil.which(argv0)
    if not found:
        return None
    path = Path(found)
    if not path.is_file():
        return None
    return path.resolve()


def _token(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > _MAX_TEXT or any(ch in value for ch in "\n\r"):
        raise ProviderIdentityError(f"{label} must be a single line")
    return value.strip()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _is_iso_z(value: object) -> bool:
    if not isinstance(value, str) or len(value) < _ISO_Z_MIN or not value.endswith("Z"):
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
