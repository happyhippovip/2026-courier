"""P9 edge pins for courier_core.verification (fail-closed verifier hand-off).

Tests only; no behavior change. Pins exact boundaries and fallbacks the
sibling P9-verification suites leave open: the 500-char reason boundary on
both the accept and worker-failure paths, non-str reason / truthy retryable
coercion on accept, the ``__qualname__`` fallback in verifier_identity, and
the empty ``__file__`` path in _source_sha256. No network, no credentials.
"""

from __future__ import annotations

import functools
import sys
import types
from pathlib import Path

from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus
from courier_core.verification import (
    Verdict,
    _source_sha256,
    run_verifier,
    verifier_identity,
)


def _task(**changes) -> TaskState:
    value = dict(task_id="t-edge", status=TaskStatus.VERIFYING,
                 adapter="synthetic", params={}, effect_class="idempotent",
                 max_attempts=3, lease_ttl_s=6, timeout_s=None)
    value.update(changes)
    return TaskState(**value)


def _ready(payload: dict) -> Event:
    return Event(type=EventType.RESULT_READY, task_id="t-edge", attempt=1,
                 dispatch_id="d-edge", worker_id="w-edge",
                 result_id="r-edge", payload=payload)


def _success(reason) -> dict:
    return {"outcome": "success",
            "artifacts": [{"path": "out.txt", "sha256": "0" * 64}],
            "reason": reason}


# -- verifier_identity: __qualname__ fallback --------------------------------

def test_identity_uses_placeholder_when_verifier_has_no_qualname(tmp_path: Path):
    def _ok(task, result, home):
        return Verdict(True, "fine", False)

    wrapped = functools.partial(_ok)
    assert getattr(wrapped, "__qualname__", "?") == "?"
    identity = verifier_identity(wrapped)
    assert identity["kind"] == "adapter"
    expected_mod = getattr(wrapped, "__module__", "?")
    assert identity["name"] == f"{expected_mod}.?"
    assert identity["version"] is None


def test_partial_verifier_still_decides_through_run_verifier(tmp_path: Path):
    def _ok(task, result, home):
        return Verdict(True, "fine", False)

    wrapped = functools.partial(_ok)
    verdict = run_verifier(lambda adapter: wrapped, _task(),
                           _ready(_success("ok")), tmp_path)
    assert verdict.accepted is True
    assert verdict.reason == "fine"
    assert verdict.verifier is not None
    assert verdict.verifier["name"].endswith(".?")


# -- accept path: reason / retryable coercion ---------------------------------

def test_accept_coerces_non_str_reason_and_truthy_retryable(tmp_path: Path):
    verdict = run_verifier(lambda adapter: lambda task, result, home: Verdict(True, None, "yes"),
                           _task(), _ready(_success("ignored")), tmp_path)
    assert verdict.accepted is True
    assert verdict.reason == "None"
    assert verdict.retryable is True
    assert verdict.verifier is not None
    assert verdict.verifier["kind"] == "adapter"


def test_accept_reason_exact_500_chars_kept_whole(tmp_path: Path):
    reason = "r" * 500
    verdict = run_verifier(lambda adapter: lambda task, result, home: Verdict(True, reason, False),
                           _task(), _ready(_success("ignored")), tmp_path)
    assert verdict.accepted is True
    assert verdict.reason == reason


def test_accept_reason_501_chars_truncated_to_500(tmp_path: Path):
    reason = "r" * 501
    verdict = run_verifier(lambda adapter: lambda task, result, home: Verdict(True, reason, False),
                           _task(), _ready(_success("ignored")), tmp_path)
    assert verdict.accepted is True
    assert verdict.reason == reason[:500]


# -- worker-failure path: 500-char reason boundary ----------------------------

def _failure(reason) -> dict:
    return {"outcome": "failure", "artifacts": [], "reason": reason}


def test_worker_failure_reason_exact_500_chars_kept_whole():
    verdict = run_verifier(lambda adapter: None, _task(),
                           _ready(_failure("f" * 500)), Path("."))
    assert verdict.accepted is False
    assert verdict.reason == "f" * 500
    assert verdict.verifier["kind"] == "courier_rule"


def test_worker_failure_reason_501_chars_truncated_to_500():
    verdict = run_verifier(lambda adapter: None, _task(),
                           _ready(_failure("f" * 501)), Path("."))
    assert verdict.accepted is False
    assert verdict.reason == "f" * 500


# -- _source_sha256: empty __file__ path ---------------------------------------

def test_source_sha256_empty_file_path_is_none(monkeypatch):
    module = types.ModuleType("edge_empty_file_module")
    module.__file__ = ""
    monkeypatch.setitem(sys.modules, "edge_empty_file_module", module)
    assert _source_sha256("edge_empty_file_module") is None
