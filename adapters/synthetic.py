"""V1 synthetic adapter (lane L4): deterministic execution + independent verification.

Execution contract (for the future worker host)::

    run(params, workdir, attempt=1) -> RunResult

``params`` are the Golden synthetic parameters (``tests/golden/README.md``):
``sleep_s``, ``write``, ``content``, ``crash_after_s``, ``hang``,
``fail_transient_n``, ``fault_attempts``. ``workdir`` is the task sandbox the
host owns; nothing is written anywhere else (no network, no subprocess, no
environment mutation). Faults apply only when ``attempt`` is listed in
``fault_attempts`` (default ``[1]``):

- ``crash_after_s`` set: sleep that long, then raise :class:`SyntheticCrash`
  (the non-zero-exit analog; the host treats it like a dead task process).
- ``hang`` true: raise :class:`SyntheticHang` (the never-finishes analog; the
  real hang behavior lives in the host timeout machinery, this keeps the fault
  deterministic and testable).
- ``attempt <= fail_transient_n``: return a retryable ``failure`` outcome
  without writing evidence (nothing was produced yet).

Otherwise sleep ``sleep_s`` and write ``content`` to ``write`` atomically
(tmp + fsync + rename) inside ``workdir``.

Verification contract (for ``courier_core.verification.run_verifier``)::

    verify(task, result, home) -> Verdict-like

``task`` is a ``TaskState``, ``result`` the journaled ``RESULT_READY`` event,
``home`` the file-scope root the caller authorizes reads from. The verifier is
pure and read-only: it never writes, never deletes, and rejected evidence is
left exactly as found (preservation is what lets a human or a retry inspect a
rejection afterwards). Dispatch identity is bound here; attempt staleness
and duplication stay the controller journal's job (fencing + dedupe keys).
Rules, fail closed:

- ``outcome != "success"`` is always rejected; ``retryable`` comes from the
  result payload, defaulting to true only for ``effect_class == "idempotent"``
  (mirrors the controller rule: nothing else becomes retryable by omission).
- when the task names a ``dispatch_id``, the result must name the same one;
  evidence bound to another (or no) dispatch is rejected. The journal fences
  stale dispatches too; this is the verifier's half of that binding.
- success requires a non-empty artifact list of ``{path, sha256}`` dicts.
- every artifact path must be workspace-relative (no absolute, drive, root or
  ``..`` under either Windows or POSIX semantics) and must resolve inside
  ``home``; the file must exist and its bytes must hash to the claimed sha256.
- when the task params declare both ``write`` and ``content``, the artifact
  named ``write`` (or ``artifacts/<dispatch_id>/<write>``, the worker host's
  per-dispatch layout) must additionally hash to the declared content (this is the
  deterministic-success pin: the bytes are what the task asked for, not merely
  self-consistent).
- anything else is rejected with a reason; unexpected internal errors are
  converted to a rejection, never raised (the controller belts this too, but a
  verifier must never depend on its caller for fail-closed behavior).

``verify`` returns a ``courier_core.verification.Verdict`` when that module is
importable (the L2-composed tree) and an identical-shape local verdict
otherwise, so the adapter is unit-testable on this lane alone. The ``verifier``
identity field is always left ``None``: ``run_verifier`` stamps it.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping

VERIFIER_VERSION = "1"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _verdict_type():
    """L2's Verdict when composed, else the identical-shape local fallback."""
    try:
        from courier_core.verification import Verdict as L2Verdict
        return L2Verdict
    except ImportError:  # lane-local testing without the L2 controller tree
        @dataclass(frozen=True)
        class LocalVerdict:
            accepted: bool
            reason: str = ""
            retryable: bool = False
            verifier: Any = None
        return LocalVerdict


def _reject(reason: str, retryable: bool = False):
    return _verdict_type()(False, str(reason)[:500], bool(retryable), None)


def _accept(reason: str):
    return _verdict_type()(True, str(reason)[:500], False, None)


class SyntheticError(ValueError):
    """Bad synthetic params or sandbox; never a verification verdict."""


class SyntheticCrash(RuntimeError):
    """Deterministic analog of a task process dying non-zero."""


class SyntheticHang(RuntimeError):
    """Deterministic analog of a task that never finishes on its own."""


def is_safe_name(name: Any) -> bool:
    """Workspace-relative names only: no absolute, drive, UNC, '..' or NUL.

    Mirrors ``scripts.artifact_store.is_safe_artifact_name`` without importing
    the legacy server path; both flavors are checked so a Windows escape that
    looks innocent to POSIX (``C:foo``, ``\\\\unc\\\\share``, rooted-driveless)
    is still refused.
    """
    if not isinstance(name, str) or not name or len(name) > 255 or "\x00" in name:
        return False
    for pure in (PureWindowsPath(name), PurePosixPath(name)):
        if pure.is_absolute() or pure.drive or pure.root or ".." in pure.parts:
            return False
    return True


def _params(params: Mapping[str, Any]) -> dict:
    """Validate synthetic params; raise SyntheticError describing the first gap."""
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


@dataclass(frozen=True)
class RunResult:
    """Outcome of :func:`run`: what the host reports to the controller."""
    outcome: str  # "success" | "failure"
    artifacts: list = field(default_factory=list)  # [{path, sha256, size}]
    reason: str = ""
    retryable: bool = False


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


def run(params: Mapping[str, Any], workdir: str | os.PathLike, attempt: int = 1) -> RunResult:
    """Execute one synthetic attempt deterministically inside ``workdir``.

    Only ``workdir`` is ever written. Faults fire only when ``attempt`` is in
    ``fault_attempts``. Raises :class:`SyntheticError` for bad params,
    :class:`SyntheticCrash` / :class:`SyntheticHang` for crash/hang faults.
    """
    cfg = _params(params)
    root = Path(workdir)
    if not isinstance(attempt, int) or attempt < 1:
        raise SyntheticError("attempt must be an int >= 1")
    faulted = attempt in cfg["fault_attempts"]
    if faulted and cfg["crash_after_s"] is not None:
        time.sleep(cfg["crash_after_s"])
        raise SyntheticCrash(f"synthetic task crashed after {cfg['crash_after_s']}s")
    if faulted and cfg["hang"]:
        raise SyntheticHang("synthetic task hangs (never finishes on its own)")
    if attempt <= cfg["fail_transient_n"]:
        return RunResult("failure", [], "synthetic transient fault", True)
    if cfg["sleep_s"]:
        time.sleep(cfg["sleep_s"])
    data = cfg["content"].encode("utf-8")
    _atomic_write(root / cfg["write"], data)
    digest = hashlib.sha256(data).hexdigest()
    return RunResult("success", [{"path": cfg["write"], "sha256": digest, "size": len(data)}])


def _payload_artifacts(payload: Mapping[str, Any]) -> list | None:
    artifacts = payload.get("artifacts", [])
    if not isinstance(artifacts, list) or not artifacts:
        return None
    return artifacts


def verify(task: Any, result: Any, home: str | os.PathLike):
    """Independently verify a RESULT_READY payload; pure and read-only.

    Returns accept only when every artifact reference resolves inside ``home``
    to bytes hashing to the claimed sha256 (plus the declared synthetic
    content when the task params pin it). Rejects everything else, including
    failures (with the controller's retryability default), evidence bound to
    another dispatch, empty or malformed evidence, missing/tampered files,
    unsafe paths, and content mismatches. Attempt staleness and duplication
    stay the controller journal's job (fencing + dedupe keys): this function
    judges evidence only and changes no state.
    """
    try:
        return _verify(task, result, home)
    except Exception as exc:  # fail closed: a verifier never raises past here
        return _reject(f"verifier internal error: {type(exc).__name__}")


def _verify(task: Any, result: Any, home: str | os.PathLike):
    payload = result.payload
    if not isinstance(payload, Mapping):
        return _reject("malformed result payload")
    if payload.get("outcome") != "success":
        reason = payload.get("reason") or "worker reported failure"
        retryable = payload.get("retryable", getattr(task, "effect_class", "") == "idempotent")
        return _reject(reason, retryable)
    task_dispatch = getattr(task, "dispatch_id", None)
    result_dispatch = getattr(result, "dispatch_id", None)
    if task_dispatch is not None and result_dispatch != task_dispatch:
        return _reject("evidence is bound to a different dispatch")
    artifacts = _payload_artifacts(payload)
    if artifacts is None:
        return _reject("missing evidence" if isinstance(payload.get("artifacts"), list) else "malformed evidence")
    try:
        scope = Path(home).resolve()
    except OSError:
        return _reject("unreadable evidence scope")
    params = getattr(task, "params", {}) or {}
    want_name = params.get("write") if isinstance(params, Mapping) else None
    want_content = params.get("content") if isinstance(params, Mapping) else None
    pinned = isinstance(want_name, str) and isinstance(want_content, str)
    want_digest = hashlib.sha256(want_content.encode("utf-8")).hexdigest() if pinned else None
    if pinned and not is_safe_name(want_name):
        return _reject("task declares an unsafe artifact name")
    # The worker host (L3) gives each dispatch its own directory and reports
    # artifacts relative to home: artifacts/<dispatch_id>/<write>. Only this
    # dispatch's directory counts, so evidence from another attempt never pins.
    want_names = set()
    if pinned:
        want_names.add(want_name)
        dispatch_id = getattr(result, "dispatch_id", None)
        if isinstance(dispatch_id, str) and is_safe_name(dispatch_id) and "/" not in dispatch_id \
                and "\\" not in dispatch_id:
            want_names.add(f"artifacts/{dispatch_id}/{PurePosixPath(want_name).as_posix()}")
    seen_pinned = False
    for ref in artifacts:
        if not isinstance(ref, Mapping):
            return _reject("malformed evidence")
        name, digest = ref.get("path"), ref.get("sha256")
        if not is_safe_name(name):
            return _reject("evidence artifact path escapes the work scope")
        if not isinstance(digest, str) or not SHA256_RE.match(digest):
            return _reject("evidence artifact sha256 is malformed")
        try:
            candidate = (scope / name).resolve()
        except OSError:
            return _reject("unreadable evidence file")
        if candidate != scope and scope not in candidate.parents:
            return _reject("evidence artifact path escapes the work scope")
        try:
            data = candidate.read_bytes()
        except OSError:
            return _reject("evidence file missing")
        if hashlib.sha256(data).hexdigest() != digest:
            return _reject("evidence artifact hash does not match")
        if pinned and name in want_names:
            seen_pinned = True
            if digest != want_digest:
                return _reject("evidence does not match the declared synthetic content")
    if pinned and not seen_pinned:
        return _reject("declared synthetic artifact is absent from the evidence")
    return _accept("synthetic evidence verified")
