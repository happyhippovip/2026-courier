"""Verifier hand-off: how the controller decides RESULT_ACCEPTED / RESULT_REJECTED.

The controller never trusts a worker's "success". After RESULT_READY is in the
journal it asks the verifier registered for the task's adapter:

    adapters/<adapter>.py:  def verify(task, result, home) -> Verdict

- task:   courier_core.state_machine.TaskState (status VERIFYING)
- result: the journaled RESULT_READY Event (artifacts, outcome, ...)
- home:   pathlib.Path of COURIER_HOME (read-only use)

Rules enforced here, independent of any adapter (fail closed):
- outcome "failure" is always rejected; retryable comes from the result
  payload. If the worker does not say, only an "idempotent" task is
  retryable: nothing else becomes retryable by omission;
- an adapter without a verifier, or a verifier that raises or returns
  something other than a Verdict, rejects non-retryably. There is no
  default PASS.

Every verdict carries `verifier`: who decided. For an adapter verifier that
is its qualified name, the module's optional VERIFIER_VERSION and the
sha256 of the module source; for the built-in rules it is the rule name.
The controller journals it with RESULT_ACCEPTED / RESULT_REJECTED.

Adapters (lane L4) own the actual evidence checks.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from courier_core.events import Event
from courier_core.state_machine import TaskState, may_auto_retry

ADAPTER_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


@dataclass(frozen=True)
class Verdict:
    accepted: bool
    reason: str = ""
    retryable: bool = False
    verifier: dict | None = None  # set by run_verifier; adapters leave it alone


VerifyFn = Callable[[TaskState, Event, Path], Verdict]


def adapter_verifier(adapter: str) -> VerifyFn | None:
    """Import adapters.<adapter>.verify; None if it does not exist."""
    if not ADAPTER_NAME.match(adapter):
        return None
    try:
        module = importlib.import_module(f"adapters.{adapter}")
    except ModuleNotFoundError as exc:
        if exc.name in ("adapters", f"adapters.{adapter}"):
            return None
        raise
    verify = getattr(module, "verify", None)
    return verify if callable(verify) else None


_SOURCE_DIGESTS: dict[tuple[str, int, int], str] = {}


def _source_sha256(module_name: str) -> str | None:
    path = getattr(sys.modules.get(module_name), "__file__", None)
    if not path:
        return None
    try:
        with open(path, "rb") as handle:
            stat = os.fstat(handle.fileno())
            key = (path, stat.st_mtime_ns, stat.st_size)
            if key not in _SOURCE_DIGESTS:
                _SOURCE_DIGESTS[key] = hashlib.sha256(handle.read()).hexdigest()
            return _SOURCE_DIGESTS[key]
    except OSError:
        return None


def verifier_identity(verify: Callable) -> dict:
    """Which verifier code produced a verdict (no PASS depends on this)."""
    module_name = getattr(verify, "__module__", None) or "?"
    version = getattr(sys.modules.get(module_name), "VERIFIER_VERSION", None)
    return {"kind": "adapter", "name": f"{module_name}.{getattr(verify, '__qualname__', '?')}",
            "version": None if version is None else str(version)[:100],
            "source_sha256": _source_sha256(module_name)}


def _rule(name: str, adapter: str) -> dict:
    return {"kind": "courier_rule", "name": name, "adapter": adapter}


def run_verifier(resolve: Callable[[str], VerifyFn | None], task: TaskState, result: Event, home: Path) -> Verdict:
    """Apply the fail-closed rules around the adapter's verdict."""
    if result.payload.get("outcome") != "success":
        retryable = result.payload.get("retryable", may_auto_retry(task.effect_class))
        reason = str(result.payload.get("reason") or "worker reported failure")
        return Verdict(False, reason[:500], bool(retryable), _rule("worker_reported_failure", task.adapter))
    try:
        verify = resolve(task.adapter)
    except Exception as exc:  # noqa: BLE001 - a broken adapter module must not PASS
        return Verdict(False, f"verifier for adapter {task.adapter!r} failed to load: {type(exc).__name__}", False,
                       _rule("verifier_load_failed", task.adapter))
    if verify is None:
        return Verdict(False, f"no verifier registered for adapter {task.adapter!r}", False,
                       _rule("no_verifier", task.adapter))
    identity = verifier_identity(verify)
    try:
        verdict = verify(task, result, home)
    except Exception as exc:  # noqa: BLE001 - fail closed
        return Verdict(False, f"verifier raised {type(exc).__name__}", False, identity)
    if not isinstance(verdict, Verdict) or not isinstance(verdict.accepted, bool):
        return Verdict(False, "verifier returned an invalid verdict", False, identity)
    return replace(verdict, reason=str(verdict.reason)[:500], retryable=bool(verdict.retryable), verifier=identity)
