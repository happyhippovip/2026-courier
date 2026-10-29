"""P9 test hardening for courier_core.verification (outcome + fail-closed pins).

Tests only; no behavior change. Covers run_verifier() worker-reported
failure handling (retryable default vs explicit, reason fallback and
truncation), the success-path fail-closed rules (no verifier, load
failure, raising verifier, invalid verdict, valid accept), adapter-name
validation boundaries, and verifier-identity shape. No network, no
credentials, no filesystem writes beyond pytest tmp_path.
"""

from __future__ import annotations

import re
import sys

import pytest

from courier_core import verification as V
from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _task(effect_class="idempotent", adapter="demo_adapter"):
    return TaskState(
        task_id="t1",
        status=TaskStatus.VERIFYING,
        adapter=adapter,
        params={},
        effect_class=effect_class,
        max_attempts=3,
        lease_ttl_s=60,
        timeout_s=30,
        attempt=1,
        dispatch_id="d-t1-1",
        worker_id="w1",
    )


def _result(outcome, retryable=None, reason=None):
    payload = {"artifacts": [], "outcome": outcome}
    if retryable is not None:
        payload["retryable"] = retryable
    if reason is not None:
        payload["reason"] = reason
    return Event(
        type=EventType.RESULT_READY,
        task_id="t1",
        attempt=1,
        dispatch_id="d-t1-1",
        worker_id="w1",
        result_id="r-t1-1",
        payload=payload,
    )


def _fail_resolve(adapter):
    raise AssertionError("resolve must not be called for a failure outcome")


def test_failure_idempotent_defaults_retryable_true(tmp_path):
    verdict = V.run_verifier(_fail_resolve, _task("idempotent"), _result("failure"), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is True
    assert verdict.reason == "worker reported failure"
    assert verdict.verifier == {"kind": "courier_rule", "name": "worker_reported_failure", "adapter": "demo_adapter"}


def test_failure_non_idempotent_defaults_retryable_false(tmp_path):
    verdict = V.run_verifier(_fail_resolve, _task("non_idempotent"), _result("failure"), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier["name"] == "worker_reported_failure"


def test_failure_explicit_retryable_false_wins_over_idempotent(tmp_path):
    verdict = V.run_verifier(
        _fail_resolve, _task("idempotent"), _result("failure", retryable=False, reason="boom"), tmp_path
    )
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.reason == "boom"


def test_failure_explicit_retryable_true_wins_over_non_idempotent(tmp_path):
    verdict = V.run_verifier(
        _fail_resolve, _task("non_idempotent"), _result("failure", retryable=True, reason="boom"), tmp_path
    )
    assert verdict.accepted is False
    assert verdict.retryable is True


def test_failure_reason_truncated_to_500(tmp_path):
    verdict = V.run_verifier(
        _fail_resolve, _task("idempotent"), _result("failure", retryable=True, reason="x" * 600), tmp_path
    )
    assert verdict.accepted is False
    assert verdict.reason == "x" * 500


def test_failure_empty_reason_falls_back_to_default(tmp_path):
    verdict = V.run_verifier(
        _fail_resolve, _task("idempotent"), _result("failure", retryable=True, reason=""), tmp_path
    )
    assert verdict.reason == "worker reported failure"


def test_success_no_verifier_rejects_non_retryably(tmp_path):
    verdict = V.run_verifier(lambda adapter: None, _task(), _result("success"), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier == {"kind": "courier_rule", "name": "no_verifier", "adapter": "demo_adapter"}
    assert "demo_adapter" in verdict.reason


def test_success_resolve_raises_rejects_with_load_failed(tmp_path):
    def _boom(adapter):
        raise RuntimeError("broken import")

    verdict = V.run_verifier(_boom, _task(), _result("success"), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier == {"kind": "courier_rule", "name": "verifier_load_failed", "adapter": "demo_adapter"}
    assert "RuntimeError" in verdict.reason


def test_success_verifier_raises_rejects_with_adapter_identity(tmp_path):
    def _bad(task, result, home):
        raise ValueError("no evidence")

    verdict = V.run_verifier(lambda adapter: _bad, _task(), _result("success"), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.reason == "verifier raised ValueError"
    assert verdict.verifier["kind"] == "adapter"
    assert verdict.verifier["name"].endswith("._bad")


def test_success_verifier_returning_non_verdict_rejects(tmp_path):
    verdict = V.run_verifier(lambda adapter: (lambda t, r, h: {"accepted": True}), _task(), _result("success"), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.reason == "verifier returned an invalid verdict"
    assert verdict.verifier["kind"] == "adapter"


def test_success_verifier_returning_non_bool_accepted_rejects(tmp_path):
    def _weird(task, result, home):
        return V.Verdict(accepted=1, reason="yes", retryable=False)

    verdict = V.run_verifier(lambda adapter: _weird, _task(), _result("success"), tmp_path)
    assert verdict.accepted is False
    assert verdict.reason == "verifier returned an invalid verdict"


def test_success_valid_accept_keeps_verdict_with_identity_and_truncation(tmp_path):
    def _ok(task, result, home):
        return V.Verdict(accepted=True, reason="y" * 600, retryable=True)

    verdict = V.run_verifier(lambda adapter: _ok, _task(), _result("success"), tmp_path)
    assert verdict.accepted is True
    assert verdict.retryable is True
    assert verdict.reason == "y" * 500
    assert verdict.verifier["kind"] == "adapter"
    assert verdict.verifier["name"].endswith("._ok")


@pytest.mark.parametrize("bad", ["", "Bad", "has-hyphen", "has space", "9digit", "UPPER", "a" * 65, "dot.name"])
def test_adapter_verifier_rejects_bad_names_without_importing(monkeypatch, bad):
    def _no_import(name):
        raise AssertionError(f"import attempted for {name!r}")

    monkeypatch.setattr(V.importlib, "import_module", _no_import)
    assert V.adapter_verifier(bad) is None


def test_adapter_verifier_missing_module_returns_none():
    assert V.adapter_verifier("no_such_adapter_xyz") is None


def test_adapter_name_boundary_64_ok_65_rejects():
    assert V.ADAPTER_NAME.match("a" * 64) is not None
    assert V.ADAPTER_NAME.match("a" * 65) is None
    assert V.adapter_verifier("a" * 65) is None


def test_verifier_identity_shape():
    def _sample(task, result, home):
        return V.Verdict(accepted=True)

    ident = V.verifier_identity(_sample)
    assert ident["kind"] == "adapter"
    assert ident["name"].endswith("._sample")
    assert ident["version"] is None or isinstance(ident["version"], str)
    assert ident["source_sha256"] is None or HEX64.match(ident["source_sha256"] or "")


def test_verifier_identity_version_truncated_to_100(monkeypatch):
    def _sample(task, result, home):
        return V.Verdict(accepted=True)

    mod = sys.modules.get(_sample.__module__)
    assert mod is not None
    monkeypatch.setattr(mod, "VERIFIER_VERSION", "v" * 150, raising=False)
    ident = V.verifier_identity(_sample)
    assert ident["version"] == "v" * 100


def test_source_sha256_unknown_module_is_none():
    assert V._source_sha256("no.such.module.xyz") is None


def test_rule_envelope_shape():
    assert V._rule("worker_reported_failure", "demo") == {
        "kind": "courier_rule",
        "name": "worker_reported_failure",
        "adapter": "demo",
    }
