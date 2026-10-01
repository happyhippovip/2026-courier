"""Verifier hand-off: how the controller decides RESULT_ACCEPTED / RESULT_REJECTED.

The controller never trusts a worker's "success". After RESULT_READY is in the
journal it asks the verifier registered for the task's adapter:

    adapters/<adapter>.py:  def verify(task, result, home) -> Verdict

- task:   courier_core.state_machine.TaskState (status VERIFYING)
- result: the journaled RESULT_READY Event (artifacts, outcome, ...)
- home:   pathlib.Path of COURIER_HOME (read-only use)

Rules enforced here, independent of any adapter (fail closed):
- outcome "failure" is always rejected; retryable comes from the result
  payload (default True: the worker reports a transient failure);
- an adapter without a verifier, or a verifier that raises or returns
  something other than a Verdict, rejects non-retryably. There is no
  default PASS.

Adapters (lane L4) own the actual evidence checks.
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from courier_core.events import Event
from courier_core.state_machine import TaskState

ADAPTER_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


@dataclass(frozen=True)
class Verdict:
    accepted: bool
    reason: str = ""
    retryable: bool = False


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


def run_verifier(resolve: Callable[[str], VerifyFn | None], task: TaskState, result: Event, home: Path) -> Verdict:
    """Apply the fail-closed rules around the adapter's verdict."""
    if result.payload.get("outcome") != "success":
        retryable = result.payload.get("retryable", True)
        reason = str(result.payload.get("reason") or "worker reported failure")
        return Verdict(False, reason[:500], bool(retryable))
    try:
        verify = resolve(task.adapter)
    except Exception as exc:  # noqa: BLE001 - a broken adapter module must not PASS
        return Verdict(False, f"verifier for adapter {task.adapter!r} failed to load: {type(exc).__name__}", False)
    if verify is None:
        return Verdict(False, f"no verifier registered for adapter {task.adapter!r}", False)
    try:
        verdict = verify(task, result, home)
    except Exception as exc:  # noqa: BLE001 - fail closed
        return Verdict(False, f"verifier raised {type(exc).__name__}", False)
    if not isinstance(verdict, Verdict):
        return Verdict(False, "verifier returned an invalid verdict", False)
    return verdict
