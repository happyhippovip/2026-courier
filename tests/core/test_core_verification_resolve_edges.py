"""P9 hardening pins for courier_core.verification resolution edges (tests only).

Covers verifier-resolution paths that have no dedicated test file in the
base tree and sit beside the open P9-verification_* PRs (contract, pins,
identity, run, resolve_pins, rules, edge, outcome, worker_failure,
failclosed, cache, hardening): all offline, no network, no subprocesses.

- ``adapter_verifier`` re-raises a ``ModuleNotFoundError`` whose name is
  foreign to the ``adapters`` package instead of swallowing it as "no
  verifier" (fail closed on unexpected import breakage, silent only on a
  genuinely missing adapter module).
- ``run_verifier`` with a ``resolve`` that returns a non-callable rejects
  non-retryably (the resulting ``TypeError`` is caught by the fail-closed
  guard) instead of crashing the controller.
- identity attribution for wrapper callables: a ``functools.partial``
  verifier is attributed as ``functools.?`` (wrapper module, no
  ``__qualname__``) with a source digest, while a callable whose
  ``__module__`` is empty falls back fully to ``"?.?"``; the success
  path attaches that identity to the verdict.

No behavior change.
"""

from __future__ import annotations

import functools
import importlib
from pathlib import Path

import pytest

from courier_core import verification as V
from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus


def _task(adapter: str = "synthetic") -> TaskState:
    return TaskState(
        task_id="t-1",
        status=TaskStatus.VERIFYING,
        adapter=adapter,
        params={},
        effect_class="default",
        max_attempts=3,
        lease_ttl_s=60,
        timeout_s=30,
    )


def _success_result() -> Event:
    return Event(
        type=EventType.RESULT_READY,
        task_id="t-1",
        attempt=1,
        dispatch_id="d-1",
        worker_id="w-1",
        result_id="r-1",
        payload={"outcome": "success", "artifacts": []},
    )


# -- adapter_verifier: foreign import breakage is re-raised ------------------


def test_adapter_verifier_reraises_foreign_module_not_found(monkeypatch):
    """A ModuleNotFoundError for anything but the adapter module itself
    propagates; only a genuinely missing adapter (or package) yields None."""

    def fake_import(name: str):
        raise ModuleNotFoundError("No module named 'foreign_dep_xyz'", name="foreign_dep_xyz")

    monkeypatch.setattr(importlib, "import_module", fake_import)
    with pytest.raises(ModuleNotFoundError):
        V.adapter_verifier("synthetic")


def test_adapter_verifier_missing_adapter_yields_none(monkeypatch):
    def fake_import(name: str):
        raise ModuleNotFoundError(f"No module named {name!r}", name=name)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    assert V.adapter_verifier("synthetic") is None
    assert V.adapter_verifier("no_such_adapter") is None


# -- run_verifier: non-callable resolve result rejects, fail closed ----------


def test_run_verifier_non_callable_resolve_result_rejects(tmp_path: Path):
    verdict = V.run_verifier(lambda _adapter: 42, _task(), _success_result(), tmp_path)
    assert verdict.accepted is False
    assert "TypeError" in verdict.reason
    assert verdict.retryable is False
    assert isinstance(verdict.verifier, dict)
    assert verdict.verifier["kind"] == "adapter"


# -- verifier_identity: callables without module metadata --------------------


def test_run_verifier_partial_identity_uses_wrapper(tmp_path: Path):
    def _check(task: TaskState, result: Event, home: Path, extra: str = ""):
        assert extra == "lane-l4"
        return V.Verdict(True, "ok", False)

    verify = functools.partial(_check, extra="lane-l4")
    verdict = V.run_verifier(lambda _adapter: verify, _task(), _success_result(), tmp_path)
    assert verdict.accepted is True
    assert verdict.reason == "ok"
    assert verdict.retryable is False
    assert verdict.verifier is not None
    assert verdict.verifier["kind"] == "adapter"
    # partial objects carry the wrapper type's module but no __qualname__.
    assert verdict.verifier["name"] == "functools.?"
    assert verdict.verifier["version"] is None
    digest = verdict.verifier["source_sha256"]
    assert isinstance(digest, str) and len(digest) == 64


def test_run_verifier_missing_module_name_falls_back(tmp_path: Path):
    class _Bare:
        def __call__(self, task: TaskState, result: Event, home: Path):
            return V.Verdict(True, "ok", False)

    verify = _Bare()
    verify.__module__ = None  # type: ignore[attr-defined]
    # Instances do not expose their type's __qualname__, so both halves
    # of the identity fall back.
    assert getattr(verify, "__qualname__", "?") == "?"
    verdict = V.run_verifier(lambda _adapter: verify, _task(), _success_result(), tmp_path)
    assert verdict.accepted is True
    assert verdict.verifier is not None
    assert verdict.verifier["name"] == "?.?"
    assert verdict.verifier["version"] is None
    assert verdict.verifier["source_sha256"] is None
