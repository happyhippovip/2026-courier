"""P9 pins for courier_core.verification (fail-closed verifier hand-off).

Tests only: no behavior change. Covers run_verifier's reject-by-default
rules, reason truncation, retryability sourcing, adapter_verifier name
gating/module lookup, and verifier_identity fields. All offline; no
network, no credentials.
"""

import hashlib
import sys
import types
from pathlib import Path

from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus
from courier_core.verification import (
    Verdict,
    adapter_verifier,
    run_verifier,
    verifier_identity,
)


def make_task(**overrides):
    value = dict(task_id="t-pin", status=TaskStatus.VERIFYING, adapter="probe_pin",
                 params={}, effect_class="idempotent", max_attempts=3,
                 lease_ttl_s=6, timeout_s=None)
    value.update(overrides)
    return TaskState(**value)


def make_ready(payload, **overrides):
    full = {"artifacts": [], "outcome": "success"}
    full.update(payload)
    value = dict(type=EventType.RESULT_READY, task_id="t-pin", attempt=1,
                 dispatch_id="d-pin", worker_id="w-pin", result_id="r-pin",
                 payload=full)
    value.update(overrides)
    return Event(**value)


def test_failure_outcome_is_rejected_with_payload_retryability(tmp_path):
    verdict = run_verifier(lambda adapter: None, make_task(),
                           make_ready({"outcome": "failure", "retryable": True,
                                       "reason": "boom"}), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is True
    assert verdict.verifier["kind"] == "courier_rule"
    assert verdict.verifier["name"] == "worker_reported_failure"

    verdict = run_verifier(lambda adapter: None, make_task(),
                           make_ready({"outcome": "failure", "retryable": False}),
                           tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False


def test_failure_without_retryable_key_falls_back_to_effect_class(tmp_path):
    idle = run_verifier(lambda adapter: None, make_task(effect_class="idempotent"),
                        make_ready({"outcome": "failure"}), tmp_path)
    assert idle.accepted is False
    assert idle.retryable is True
    assert idle.reason == "worker reported failure"

    consequential = run_verifier(
        lambda adapter: None, make_task(effect_class="consequential"),
        make_ready({"outcome": "failure"}), tmp_path)
    assert consequential.accepted is False
    assert consequential.retryable is False


def test_failure_reason_truncated_to_500_chars(tmp_path):
    verdict = run_verifier(lambda adapter: None, make_task(),
                           make_ready({"outcome": "failure", "reason": "x" * 900}),
                           tmp_path)
    assert len(verdict.reason) == 500


def test_resolve_exception_rejects_as_load_failed(tmp_path):
    def resolve(adapter):
        raise RuntimeError("broken registry")

    verdict = run_verifier(resolve, make_task(),
                           make_ready({"outcome": "success"}), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier["name"] == "verifier_load_failed"
    assert "probe_pin" in verdict.reason


def test_missing_verifier_rejects_as_no_verifier(tmp_path):
    verdict = run_verifier(lambda adapter: None, make_task(),
                           make_ready({"outcome": "success"}), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier["name"] == "no_verifier"


def test_verifier_exception_rejects_and_carries_identity(tmp_path):
    def verify(task, result, home):
        raise ValueError("adapter blew up")

    verdict = run_verifier(lambda adapter: verify, make_task(),
                           make_ready({"outcome": "success"}), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert "ValueError" in verdict.reason
    assert verdict.verifier["kind"] == "adapter"
    assert verdict.verifier["name"].endswith(".verify")


def test_non_verdict_return_rejects(tmp_path):
    verdict = run_verifier(lambda adapter: (lambda t, r, h: "looks fine"),
                           make_task(), make_ready({"outcome": "success"}),
                           tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier["kind"] == "adapter"


def test_non_bool_accepted_rejects(tmp_path):
    def verify(task, result, home):
        return Verdict("yes", "stringly accepted")

    verdict = run_verifier(lambda adapter: verify, make_task(),
                           make_ready({"outcome": "success"}), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False


def test_accept_is_stamped_with_identity_and_truncated_reason(tmp_path):
    def verify(task, result, home):
        return Verdict(True, "y" * 800, retryable=1)

    verdict = run_verifier(lambda adapter: verify, make_task(),
                           make_ready({"outcome": "success"}), tmp_path)
    assert verdict.accepted is True
    assert len(verdict.reason) == 500
    assert verdict.retryable is True
    assert verdict.verifier["kind"] == "adapter"


def test_adapter_verifier_rejects_bad_names_without_importing():
    for bad in ("", "Has-Caps", "has space", "a" * 65, "../evil",
                "9-starts-with-digit", "semi;colon"):
        assert adapter_verifier(bad) is None


def test_adapter_verifier_missing_module_returns_none():
    assert adapter_verifier("no_such_adapter_xyz_123") is None


def test_adapter_verifier_returns_registered_verify(monkeypatch):
    module = types.ModuleType("adapters.probe_pin_test")

    def verify(task, result, home):
        return Verdict(True, "ok")

    module.verify = verify
    monkeypatch.setitem(sys.modules, "adapters.probe_pin_test", module)
    assert adapter_verifier("probe_pin_test") is verify


def test_adapter_verifier_without_verify_attr_returns_none(monkeypatch):
    monkeypatch.setitem(sys.modules, "adapters.probe_pin_empty",
                        types.ModuleType("adapters.probe_pin_empty"))
    assert adapter_verifier("probe_pin_empty") is None


def sample_verify(task, result, home):
    return Verdict(True, "ok")


def test_verifier_identity_fields_for_module_function():
    identity = verifier_identity(sample_verify)
    assert identity["kind"] == "adapter"
    assert identity["name"] == f"{__name__}.sample_verify"
    assert identity["version"] is None
    assert identity["source_sha256"] == hashlib.sha256(
        Path(__file__).read_bytes()).hexdigest()


def test_verifier_identity_truncates_long_version(monkeypatch):
    module = types.ModuleType("probe_pin_versioned")
    module.__file__ = __file__
    module.VERIFIER_VERSION = "v" * 150
    monkeypatch.setitem(sys.modules, "probe_pin_versioned", module)

    def verify(task, result, home):
        return Verdict(True, "ok")

    verify.__module__ = "probe_pin_versioned"
    identity = verifier_identity(verify)
    assert identity["version"] == "v" * 100


def test_verifier_identity_without_source_file_gives_none_digest(monkeypatch):
    module = types.ModuleType("probe_pin_nofile")
    module.__file__ = "/nonexistent/path/probe_pin_nofile.py"
    monkeypatch.setitem(sys.modules, "probe_pin_nofile", module)

    def verify(task, result, home):
        return Verdict(True, "ok")

    verify.__module__ = "probe_pin_nofile"
    assert verifier_identity(verify)["source_sha256"] is None
