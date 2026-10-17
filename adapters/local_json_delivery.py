"""Local JSON delivery adapter (lane L4): deterministic delivery + independent verification.

Execution contract (for worker host)::

    run(params, workdir, attempt=1) -> RunResult

Takes news article params (conforming to NewsArticle schema), delivers them
as an atomic JSON file inside ``workdir``, and returns structured artifacts with
sha256 digest.

Verification contract (for courier_core.verification.run_verifier)::

    verify(task, result, home) -> Verdict

Independently checks that the delivered article file exists inside ``home``,
its sha256 matches the on-disk bytes, and its JSON content faithfully matches
the task's article parameters (article_id, title).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping

VERIFIER_VERSION = "1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_ARTIFACTS = 16


def _verdict_type():
    """L2's Verdict when composed, else the identical-shape local fallback."""
    try:
        from courier_core.verification import Verdict as L2Verdict
        return L2Verdict
    except ImportError:
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


class DeliveryError(ValueError):
    """Bad delivery params or workdir."""


@dataclass(frozen=True)
class RunResult:
    outcome: str  # "success" | "failure"
    artifacts: list = field(default_factory=list)  # [{path, sha256, size}]
    reason: str = ""
    retryable: bool = False


def is_safe_name(name: Any) -> bool:
    """Workspace-relative names only: no absolute, drive, UNC, '..' or NUL."""
    if not isinstance(name, str) or not name or len(name) > 255 or "\x00" in name:
        return False
    for pure in (PureWindowsPath(name), PurePosixPath(name)):
        if pure.is_absolute() or pure.drive or pure.root or ".." in pure.parts:
            return False
    return True


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
    """Execute local JSON delivery inside ``workdir``."""
    if not isinstance(params, Mapping):
        raise DeliveryError("params must be a mapping")
    article_id = params.get("article_id")
    if not isinstance(article_id, str) or not article_id:
        raise DeliveryError("missing article_id")

    safe_filename = f"{article_id}.json"
    if not is_safe_name(safe_filename):
        raise DeliveryError("article_id produces an unsafe file name")

    root = Path(workdir)
    target = root / safe_filename

    encoded = json.dumps(dict(params), indent=2, sort_keys=True).encode("utf-8")
    _atomic_write(target, encoded)

    digest = hashlib.sha256(encoded).hexdigest()
    return RunResult(
        outcome="success",
        artifacts=[{
            "path": safe_filename,
            "sha256": digest,
            "size": len(encoded),
        }],
    )


def verify(task: Any, result: Any, home: str | os.PathLike):
    """Independently verify a RESULT_READY payload for local_json_delivery."""
    try:
        return _verify(task, result, home)
    except Exception as exc:  # fail closed
        return _reject(f"verifier internal error: {type(exc).__name__}")


def _verify(task: Any, result: Any, home: str | os.PathLike):
    payload = getattr(result, "payload", None)
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

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return _reject("missing evidence")
    if len(artifacts) > MAX_ARTIFACTS:
        return _reject("evidence exceeds artifact count budget")

    try:
        scope = Path(home).resolve()
    except OSError:
        return _reject("unreadable evidence scope")

    params = getattr(task, "params", {}) or {}
    want_article_id = params.get("article_id") if isinstance(params, Mapping) else None
    want_filename = f"{want_article_id}.json" if want_article_id else None

    # Track artifact match
    found_article = False

    for ref in artifacts:
        if not isinstance(ref, Mapping):
            return _reject("malformed evidence")
        name = ref.get("path")
        digest = ref.get("sha256")

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

        # Verify JSON content matches article
        try:
            article_data = json.loads(data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return _reject("evidence article is not valid JSON")

        if want_article_id is not None:
            if article_data.get("article_id") != want_article_id:
                return _reject("delivered article_id does not match task params")
            if "title" in params and article_data.get("title") != params["title"]:
                return _reject("delivered title does not match task params")
            found_article = True

    if want_article_id is not None and not found_article:
        return _reject("expected article artifact not found in evidence")

    return _accept("local_json_delivery evidence verified")
