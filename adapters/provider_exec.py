"""Controller verifier for the provider_exec adapter.

The worker adapter lives in ``courier_worker.adapters.provider_exec``. This
module is the other half: ``courier_core.verification.adapter_verifier``
imports ``adapters.provider_exec.verify``. No registry edit is required.

``verify(task, result, home)`` is pure and read-only. It accepts only when
every declared artifact is a regular file inside ``home``, at most 1 MiB,
whose bytes match the claimed sha256; ``provider_output.txt`` is one of those
artifacts; and each ``task.params["expected_outputs"]`` entry exists in the
task workspace (``params["workspace"]`` under ``home``), directly under
``home``, or under ``artifacts/<dispatch_id>/``, matching a pinned sha256
and/or exact utf-8 content. A non-zero Muse exit is rejected even when
``outcome`` says success. Symlink escapes, path traversal, oversized files,
and missing evidence are rejected. Replay is a second call with the same
inputs: nothing is written or deleted.

The runner write of ``provider_output.txt`` belongs to
``courier_worker/adapter_runner.py`` (open PRs #141 and #165). This module
does not perform that write.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from adapters.synthetic import SHA256_RE, is_safe_name

VERIFIER_VERSION = "1"
EVIDENCE_NAME = "provider_output.txt"
MAX_EVIDENCE_BYTES = 1024 * 1024  # 1 MiB

_EXIT_RE = re.compile(r"(?:^|\s)exit=(-?\d+)\b")


def _verdict_type():
    """L2's Verdict when composed, else the identical-shape local fallback."""
    try:
        from courier_core.verification import Verdict as L2Verdict
        return L2Verdict
    except ImportError:  # lane-local testing without the L2 controller tree
        from dataclasses import dataclass

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


def _exit_rejection(payload: Mapping[str, Any]) -> str | None:
    """A claimed success still fails when the Muse exit is not zero."""
    if "exit_code" in payload:
        code = payload.get("exit_code")
        if isinstance(code, bool) or not isinstance(code, int):
            return "malformed muse exit"
        if code != 0:
            return "non-zero muse exit"
    reason = payload.get("reason")
    if isinstance(reason, str) and reason:
        if "NONZERO_EXIT" in reason:
            return "non-zero muse exit"
        match = _EXIT_RE.search(reason)
        if match and int(match.group(1)) != 0:
            return "non-zero muse exit"
    return None


def _read_inside(scope: Path, rel: str):
    """Return ``(bytes, None)`` or ``(None, reason)``. Never follows an escape."""
    if not isinstance(rel, str) or not is_safe_name(rel):
        return None, "evidence artifact path escapes the work scope"
    raw = scope / rel
    try:
        candidate = raw.resolve()
    except OSError:
        return None, "unreadable evidence file"
    if candidate != scope and scope not in candidate.parents:
        return None, "evidence artifact path escapes the work scope"
    try:
        info = candidate.lstat()
    except OSError:
        return None, "evidence file missing"
    if stat.S_ISLNK(info.st_mode):
        return None, "evidence artifact path escapes the work scope"
    if not stat.S_ISREG(info.st_mode):
        return None, "evidence file missing"
    if info.st_size > MAX_EVIDENCE_BYTES:
        return None, "evidence file exceeds 1 MiB"
    try:
        with open(candidate, "rb") as handle:
            data = handle.read(MAX_EVIDENCE_BYTES + 1)
    except OSError:
        return None, "unreadable evidence file"
    if len(data) > MAX_EVIDENCE_BYTES:
        return None, "evidence file exceeds 1 MiB"
    return data, None


def _locate(scope: Path, declared: str, workspace: Any, dispatch_id: Any):
    """First existing candidate inside the workspace, home, or dispatch dir."""
    if not isinstance(declared, str) or not is_safe_name(declared):
        return None, "declared output path escapes the work scope"
    names: list[str] = []
    if workspace not in (None, ""):
        if not isinstance(workspace, str) or not is_safe_name(workspace):
            return None, "task workspace escapes the work scope"
        names.append(
            f"{PurePosixPath(workspace).as_posix()}/{PurePosixPath(declared).as_posix()}")
    names.append(PurePosixPath(declared).as_posix())
    if (isinstance(dispatch_id, str) and is_safe_name(dispatch_id)
            and "/" not in dispatch_id and "\\" not in dispatch_id):
        names.append(f"artifacts/{dispatch_id}/{PurePosixPath(declared).as_posix()}")
    ordered: list[str] = []
    for name in names:
        if name not in ordered:
            ordered.append(name)
    for name in ordered:
        if not is_safe_name(name):
            return None, "declared output path escapes the work scope"
        raw = scope / name
        try:
            present = raw.is_symlink() or raw.is_file()
        except OSError:
            return None, "unreadable evidence file"
        if present:
            return name, None
    return None, "declared output is missing"


def _check_expected(scope: Path, params: Mapping[str, Any], dispatch_id: Any):
    if "expected_outputs" not in params:
        return None
    expected = params.get("expected_outputs")
    if not isinstance(expected, list):
        return _reject("malformed declared outputs")
    workspace = params.get("workspace")
    for entry in expected:
        if not isinstance(entry, Mapping):
            return _reject("malformed declared outputs")
        found, why = _locate(scope, entry.get("path"), workspace, dispatch_id)
        if found is None:
            return _reject(why or "declared output is missing")
        data, read_why = _read_inside(scope, found)
        if data is None:
            return _reject(read_why or "unreadable evidence file")
        has_pin = False
        if "content" in entry:
            has_pin = True
            content = entry.get("content")
            if not isinstance(content, str) or data != content.encode("utf-8"):
                return _reject("evidence does not match the declared content")
        if "sha256" in entry:
            has_pin = True
            pinned = entry.get("sha256")
            if not isinstance(pinned, str) or not SHA256_RE.match(pinned):
                return _reject("declared output sha256 is malformed")
            if hashlib.sha256(data).hexdigest() != pinned:
                return _reject("evidence does not match the declared sha256")
        if not has_pin:
            return _reject("declared output has no pin")
    return None


def verify(task: Any, result: Any, home: str | os.PathLike):
    """Independently verify a provider_exec RESULT_READY. Pure and read-only."""
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
    exit_reason = _exit_rejection(payload)
    if exit_reason:
        return _reject(exit_reason)
    task_dispatch = getattr(task, "dispatch_id", None)
    result_dispatch = getattr(result, "dispatch_id", None)
    if task_dispatch is not None and result_dispatch != task_dispatch:
        return _reject("evidence is bound to a different dispatch")
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return _reject("missing evidence" if isinstance(artifacts, list) else "malformed evidence")
    try:
        scope = Path(home).resolve()
    except OSError:
        return _reject("unreadable evidence scope")
    if not scope.is_dir():
        return _reject("unreadable evidence scope")
    evidence = 0
    for ref in artifacts:
        if not isinstance(ref, Mapping):
            return _reject("malformed evidence")
        name, digest = ref.get("path"), ref.get("sha256")
        if isinstance(name, str) and PurePosixPath(name).name == EVIDENCE_NAME:
            evidence += 1
        if not isinstance(digest, str) or not SHA256_RE.match(digest):
            return _reject("evidence artifact sha256 is malformed")
        data, why = _read_inside(scope, name)
        if data is None:
            return _reject(why or "unreadable evidence file")
        if hashlib.sha256(data).hexdigest() != digest:
            return _reject("evidence artifact hash does not match")
    if evidence != 1:
        return _reject("missing evidence" if evidence == 0 else "ambiguous evidence file")
    params = getattr(task, "params", {}) or {}
    if not isinstance(params, Mapping):
        return _reject("malformed task spec")
    pinned = _check_expected(scope, params, result_dispatch)
    if pinned is not None:
        return pinned
    return _accept("provider_exec evidence verified")
