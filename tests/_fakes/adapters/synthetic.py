"""Test-harness double for the trusted ``synthetic`` adapter (lane L4).

Scope: lane-local L3 tests ONLY. This module is never imported by product
code and never ships to a worker. It mirrors the observable contract the L3
bridge depends on (param validation outcomes, fault gating by attempt number,
crash/hang signalling, artifact bytes + sha256) so the L3 suite proves
allowlist/envelope/outbox behavior without owning L4 source.

Anything security-relevant (path confinement, hash binding) is re-checked by
the real L4 module in composition; this double exists so missing L4 source
fails L3 tests loudly at import/setup time instead of silently skipping them.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import SimpleNamespace
from typing import Any, Mapping


class SyntheticError(Exception):
    """Bad params; the bridge turns this into SpecError."""


class SyntheticCrash(Exception):
    """The attempt crashed; the runner reports returncode 3."""


class SyntheticHang(Exception):
    """The attempt hangs; the host timeout machinery owns termination."""


def is_safe_name(name: Any) -> bool:
    """Workspace-relative names only: no absolute, drive, UNC, '..' or NUL."""
    if not isinstance(name, str) or not name or len(name) > 255 or "\x00" in name:
        return False
    for pure in (PureWindowsPath(name), PurePosixPath(name)):
        if pure.is_absolute() or pure.drive or pure.root or ".." in pure.parts:
            return False
    return True


def _params(params: Mapping[str, Any]) -> dict:
    """Validate synthetic params; raise SyntheticError describing the gap."""
    if not isinstance(params, Mapping):
        raise SyntheticError("synthetic params must be a mapping")
    out = {
        "sleep_s": params.get("sleep_s", 0),
        "write": params.get("write", "out.txt"),
        "content": params.get("content", ""),
        "crash_after_s": params.get("crash_after_s", None),
        "hang": params.get("hang", False),
        "fail_transient_n": params.get("fail_transient_n", 0),
        "fault_attempts": params.get("fault_attempts", [1]),
    }
    if not isinstance(out["sleep_s"], (int, float)) or not (out["sleep_s"] >= 0):
        raise SyntheticError("sleep_s must be a non-negative number")
    if not isinstance(out["write"], str) or not is_safe_name(out["write"]):
        raise SyntheticError("write must be a safe workspace-relative file name")
    if not isinstance(out["content"], str):
        raise SyntheticError("content must be a string")
    if out["crash_after_s"] is not None and (
            not isinstance(out["crash_after_s"], (int, float)) or not (out["crash_after_s"] >= 0)):
        raise SyntheticError("crash_after_s must be null or a non-negative number")
    if not isinstance(out["hang"], bool):
        raise SyntheticError("hang must be a boolean")
    if not isinstance(out["fail_transient_n"], int) or out["fail_transient_n"] < 0:
        raise SyntheticError("fail_transient_n must be a non-negative int")
    if (not isinstance(out["fault_attempts"], list) or not out["fault_attempts"]
            or any(not isinstance(a, int) or a < 1 for a in out["fault_attempts"])):
        raise SyntheticError("fault_attempts must be a non-empty list of attempts >= 1")
    return out


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def run(params: Mapping[str, Any], workdir: str | os.PathLike, attempt: int = 1) -> SimpleNamespace:
    """Execute one synthetic attempt deterministically inside ``workdir``.

    Faults fire only when ``attempt`` is in ``fault_attempts``. Only
    ``workdir`` is ever written.
    """
    import time
    cfg = _params(params)
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        raise SyntheticError("attempt must be an int >= 1")
    faulted = attempt in cfg["fault_attempts"]
    if faulted and cfg["crash_after_s"] is not None:
        raise SyntheticCrash(f"synthetic task crashed after {cfg['crash_after_s']}s")
    if faulted and cfg["hang"]:
        raise SyntheticHang("synthetic task hangs (never finishes on its own)")
    if attempt <= cfg["fail_transient_n"]:
        return SimpleNamespace(outcome="failure", artifacts=[],
                               reason="synthetic transient fault", retryable=True)
    if cfg["sleep_s"]:
        time.sleep(cfg["sleep_s"])
    data = cfg["content"].encode("utf-8")
    root = Path(workdir)
    _atomic_write(root / cfg["write"], data)
    digest = hashlib.sha256(data).hexdigest()
    return SimpleNamespace(outcome="success",
                           artifacts=[{"path": cfg["write"], "sha256": digest, "size": len(data)}],
                           reason="synthetic execution complete", retryable=False)
