"""Canonical worker availability resolver for Courier.

Provides deterministic, testable availability resolution for all workers
(GEMINI/AGY, CLI1, CODEX) with fingerprinting to detect transitions and
support safe, bounded retry/replan.

Resolution precedence for AGY/GEMINI:
  1. Explicitly configured agy_path (if provided and valid)
  2. PATH discovery  ('which agy')
  3. Known canonical installation path as fallback

Model calls: 0
Network: 0
Spend: 0
"""
from __future__ import annotations

import hashlib
import json
import os
import contextlib
import fcntl
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional

# Known canonical install path; used only as last-resort fallback after PATH.
_DEFAULT_AGY_PATH = Path("/Users/user/.local/bin/agy")


class WorkerState:
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class AvailabilityStoreIntegrityError(RuntimeError):
    """Persisted availability history is malformed and cannot be trusted."""


@dataclass(frozen=True)
class AvailabilityEvidence:
    """Structured evidence returned by the resolver — never fabricated."""
    worker: str               # "GEMINI", "CLI1", "CODEX"
    state: str                # WorkerState value
    executable: Optional[str]  # Resolved path if found, else None
    resolution_method: str    # e.g. "CONFIGURED_PATH", "PATH_DISCOVERY", "CANONICAL_FALLBACK"
    detail: str               # Human-readable one-liner

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def fingerprint(self) -> str:
        """Changes when meaningful execution availability changes (path or state)."""
        key = {"worker": self.worker, "state": self.state, "executable": self.executable}
        raw = json.dumps(key, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()


def _is_executable(path: Path) -> bool:
    """True if the file exists and is executable (no sandbox bypass)."""
    try:
        return path.exists() and os.access(path, os.X_OK)
    except Exception:
        return False


def _find_in_PATH(name: str) -> Optional[Path]:
    """Return first directory in PATH containing an executable `name`."""
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(directory) / name
        if _is_executable(candidate):
            return candidate
    return None


class WorkerAvailabilityResolver:
    """Single canonical resolver — deterministic and testable.

    Inject ``agy_path_override`` in tests to control resolution without
    touching real filesystem state.
    """

    def __init__(self, agy_path_override: Optional[Path] = None) -> None:
        self._agy_override = agy_path_override

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def resolve_gemini(self) -> AvailabilityEvidence:
        """Resolve GEMINI/AGY availability.  Precedence:
          1. Configured override (test injection or explicit configuration)
          2. PATH discovery
          3. Canonical fallback path
        """
        # 1. Explicit configuration / test injection
        if self._agy_override is not None:
            path = self._agy_override
            ok = _is_executable(path)
            return AvailabilityEvidence(
                worker="GEMINI",
                state=WorkerState.AVAILABLE if ok else WorkerState.UNAVAILABLE,
                executable=str(path) if ok else None,
                resolution_method="CONFIGURED_PATH",
                detail=f"Configured path {'found and executable' if ok else 'not executable'}: {path}",
            )

        # 2. PATH discovery
        found = _find_in_PATH("agy")
        if found is not None:
            return AvailabilityEvidence(
                worker="GEMINI",
                state=WorkerState.AVAILABLE,
                executable=str(found),
                resolution_method="PATH_DISCOVERY",
                detail=f"agy found in PATH: {found}",
            )

        # 3. Canonical fallback
        path = _DEFAULT_AGY_PATH
        ok = _is_executable(path)
        return AvailabilityEvidence(
            worker="GEMINI",
            state=WorkerState.AVAILABLE if ok else WorkerState.UNAVAILABLE,
            executable=str(path) if ok else None,
            resolution_method="CANONICAL_FALLBACK",
            detail=f"Canonical path {'executable' if ok else 'not found/not executable'}: {path}",
        )

    def resolve_cli1(self) -> AvailabilityEvidence:
        """CLI1 is a local deterministic worker — always available."""
        return AvailabilityEvidence(
            worker="CLI1",
            state=WorkerState.AVAILABLE,
            executable="python3",
            resolution_method="INTRINSIC",
            detail="CLI1 is a deterministic local worker, inherently available.",
        )

    def resolve_codex(self) -> AvailabilityEvidence:
        """Resolve CODEX (ChatGPT native CLI) availability."""
        codex_path = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
        found = _find_in_PATH("codex")
        if found:
            return AvailabilityEvidence(
                worker="CODEX",
                state=WorkerState.AVAILABLE,
                executable=str(found),
                resolution_method="PATH_DISCOVERY",
                detail=f"codex found in PATH: {found}",
            )
        if _is_executable(codex_path):
            return AvailabilityEvidence(
                worker="CODEX",
                state=WorkerState.AVAILABLE,
                executable=str(codex_path),
                resolution_method="CANONICAL_FALLBACK",
                detail=f"codex found at canonical path: {codex_path}",
            )
        return AvailabilityEvidence(
            worker="CODEX",
            state=WorkerState.UNAVAILABLE,
            executable=None,
            resolution_method="CANONICAL_FALLBACK",
            detail=f"codex not found in PATH or at {codex_path}",
        )

    def resolve(self, worker: str) -> AvailabilityEvidence:
        """Resolve availability for a named worker."""
        if worker == "GEMINI":
            return self.resolve_gemini()
        if worker == "CLI1":
            return self.resolve_cli1()
        if worker == "CODEX":
            return self.resolve_codex()
        return AvailabilityEvidence(
            worker=worker,
            state=WorkerState.UNAVAILABLE,
            executable=None,
            resolution_method="UNKNOWN_WORKER",
            detail=f"Unrecognised worker: {worker}",
        )


class AvailabilityStore:
    """Persist availability fingerprints so the system can detect transitions."""

    def __init__(self, workspace_dir: Path) -> None:
        self._path = workspace_dir / "events" / "worker-availability" / "fingerprints.json"
        self._lock_path = self._path.with_suffix(".lock")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._locked():
            if not self._path.exists():
                self._write({})

    @contextlib.contextmanager
    def _locked(self):
        with open(self._lock_path, "a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _read(self) -> Dict[str, Any]:
        try:
            with open(self._path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as error:
            raise AvailabilityStoreIntegrityError("WORKER_AVAILABILITY_CORRUPT_FAIL_CLOSED") from error
        if not isinstance(data, dict) or not all(
            isinstance(worker, str) and isinstance(fingerprint, str)
            for worker, fingerprint in data.items()
        ):
            raise AvailabilityStoreIntegrityError("WORKER_AVAILABILITY_CORRUPT_FAIL_CLOSED")
        return data

    def _write(self, data: Dict[str, Any]) -> None:
        tmp = self._path.with_name(f".{self._path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self._path)
        finally:
            tmp.unlink(missing_ok=True)

    def get_last(self, worker: str) -> Optional[str]:
        """Return last persisted fingerprint for ``worker``, or None."""
        return self._read().get(worker)

    def update(self, worker: str, fingerprint: str) -> None:
        """Persist the latest availability fingerprint for ``worker``."""
        with self._locked():
            data = self._read()
            data[worker] = fingerprint
            self._write(data)

    def classify_transition(self, worker: str, current: AvailabilityEvidence) -> str:
        """Return one of: AVAILABLE, UNAVAILABLE, CHANGED_SINCE_LAST_CHECK, UNCHANGED."""
        current_fp = current.fingerprint()
        with self._locked():
            data = self._read()
            last_fp = data.get(worker)
            data[worker] = current_fp
            self._write(data)

        if last_fp is None:
            return current.state

        if current_fp == last_fp:
            return "UNCHANGED"

        return "CHANGED_SINCE_LAST_CHECK"
