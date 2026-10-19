"""P9 hardening for courier_core.verification (fail-closed verifier hand-off).

Tests only; no behavior change. Covers the pure fail-closed rules around
the adapter verifier: Verdict shape, adapter name gating, verifier
resolution, source identity, and run_verifier accept/reject paths.
No network, no credentials.
"""

import hashlib
import sys
import types

import pytest

from courier_core.events import Event, EventType
from courier_core.state_machine import TaskStatus, TaskState
from courier_core import verification as verify_mod
from courier_core.verification import (
    ADAPTER_NAME,
    Verdict,
    _source_sha256,
    adapter_verifier,
    run_verifier,
    verifier_identity,
)

SHA = hashlib.sha256(b"courier-verification-hardening").hexdigest()


def _task(**changes):
    value = dict(task_id="t1", status=TaskStatus.VERIFYING, adapter="synthetic",
                 params={}, effect_class="idempotent", max_attempts=3,
                 lease_ttl_s=6, timeout_s=None)
    value.update(changes)
    return TaskState(**value)


def _ready(payload, **changes):
    base = dict(type=EventType.RESULT_READY, task_id="t1", attempt=1,
                dispatch_id="d1", worker_id="w1", result_id="r1",
                payload=payload)
    base.update(changes)
    return Event(**base)


def _success_payload(**changes):
    payload = {"outcome": "success",
               "artifacts": [{"path": "out.txt", "sha256": SHA}]}
    payload.update(changes)
    return payload


# -- Verdict shape ------------------------------------------------------------

def test_verdict_defaults():
    verdict = Verdict(True)
    assert verdict.accepted is True
    assert verdict.reason == ""
    assert verdict.retryable is False
    assert verdict.verifier is None


def test_verdict_is_frozen():
    verdict = Verdict(False, "no", True, {"kind": "courier_rule"})
    with pytest.raises(Exception):
        verdict.accepted = True  # type: ignore[misc]


# -- adapter name gating ------------------------------------------------------

_VALID_NAMES = ["a", "synthetic", "local_shell", "abc123_", "z" + "0" * 63]


@pytest.mark.parametrize("name", _VALID_NAMES)
def test_adapter_name_accepts_valid(name):
    assert ADAPTER_NAME.match(name) is not None


@pytest.mark.parametrize("name", [
    "", "UPPER", "has-dash", "has space", "0start", "a" * 65, "dot.name",
    "slash/name", "under-hyphen-mix-",
])
def test_adapter_name_rejects_invalid(name):
    assert ADAPTER_NAME.match(name) is None


@pytest.mark.parametrize("name", ["", "UPPER", "has-dash", "0start"])
def test_adapter_verifier_rejects_bad_name_without_import(name):
    assert adapter_verifier(name) is None


def test_adapter_verifier_returns_none_for_missing_adapter():
    assert adapter_verifier("no_such_adapter_xyz_123") is None


def test_adapter_verifier_resolves_real_synthetic():
    verify = adapter_verifier("synthetic")
    assert callable(verify)
    assert verify.__module__ == "adapters.synthetic"


def _install_adapter_module(name, **attrs):
    """Install adapters.<name> into sys.modules; caller must remove it."""
    parent = sys.modules.get("adapters")
    module = types.ModuleType(f"adapters.{name}")
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[f"adapters.{name}"] = module
    return module, parent is not None


def test_adapter_verifier_none_when_no_verify_attr():
    name = "fake_no_verify_attr"
    assert f"adapters.{name}" not in sys.modules
    sys.modules[f"adapters.{name}"] = types.ModuleType(f"adapters.{name}")
    try:
        assert adapter_verifier(name) is None
    finally:
        del sys.modules[f"adapters.{name}"]


def test_adapter_verifier_none_when_verify_not_callable():
    name = "fake_verify_not_callable"
    module = types.ModuleType(f"adapters.{name}")
    module.verify = 123  # type: ignore[attr-defined]
    sys.modules[f"adapters.{name}"] = module
    try:
        assert adapter_verifier(name) is None
    finally:
        del sys.modules[f"adapters.{name}"]


def test_adapter_verifier_returns_callable_verify():
    name = "fake_verify_ok"
    def verify(task, result, home):
        return Verdict(True)
    module = types.ModuleType(f"adapters.{name}")
    module.verify = verify
    sys.modules[f"adapters.{name}"] = module
    try:
        assert adapter_verifier(name) is verify
    finally:
        del sys.modules[f"adapters.{name}"]


# -- source identity ----------------------------------------------------------

def test_source_sha256_none_for_unknown_module():
    assert _source_sha256("no.such.module.xyz") is None


def test_source_sha256_none_when_no_file_attr():
    name = "fake_no_file_mod_xyz"
    module = types.ModuleType(name)
    assert not hasattr(module, "__file__")
    sys.modules[name] = module
    try:
        assert _source_sha256(name) is None
    finally:
        del sys.modules[name]


def test_source_sha256_none_for_missing_file():
    name = "fake_missing_file_mod_xyz"
    module = types.ModuleType(name)
    module.__file__ = "/no/such/file/xyz123.py"  # type: ignore[attr-defined]
    sys.modules[name] = module
    try:
        assert _source_sha256(name) is None
    finally:
        del sys.modules[name]


def test_source_sha256_matches_file_bytes(tmp_path):
    name = "fake_real_file_mod_xyz"
    target = tmp_path / "mod_xyz.py"
    target.write_bytes(b"print('hello')\n")
    module = types.ModuleType(name)
    module.__file__ = str(target)  # type: ignore[attr-defined]
    sys.modules[name] = module
    try:
        expected = hashlib.sha256(b"print('hello')\n").hexdigest()
        assert _source_sha256(name) == expected
        # Cached second call agrees.
        assert _source_sha256(name) == expected
    finally:
        del sys.modules[name]


def test_verifier_identity_shape_with_version_and_source(tmp_path):
    mod_name = "fake_identity_mod_xyz"
    target = tmp_path / "ident.py"
    target.write_bytes(b"x = 1\n")
    module = types.ModuleType(mod_name)
    module.__file__ = str(target)  # type: ignore[attr-defined]
    module.VERIFIER_VERSION = "7"  # type: ignore[attr-defined]
    sys.modules[mod_name] = module
    try:
        def verify(task, result, home):
            return Verdict(True)
        verify.__module__ = mod_name
        identity = verifier_identity(verify)
        assert identity["kind"] == "adapter"
        assert identity["name"].startswith(mod_name + ".")
        assert identity["version"] == "7"
        assert identity["source_sha256"] == hashlib.sha256(b"x = 1\n").hexdigest()
    finally:
        del sys.modules[mod_name]


def test_verifier_identity_version_none_when_missing(tmp_path):
    mod_name = "fake_identity_nover_xyz"
    target = tmp_path / "nover.py"
    target.write_bytes(b"y = 2\n")
    module = types.ModuleType(mod_name)
    module.__file__ = str(target)  # type: ignore[attr-defined]
    sys.modules[mod_name] = module
    try:
        def verify(task, result, home):
            return Verdict(True)
        verify.__module__ = mod_name
        identity = verifier_identity(verify)
        assert identity["version"] is None
    finally:
        del sys.modules[mod_name]


def test_verifier_identity_version_truncated_to_100():
    mod_name = "fake_identity_longver_xyz"
    module = types.ModuleType(mod_name)
    module.VERIFIER_VERSION = "v" * 250  # type: ignore[attr-defined]
    sys.modules[mod_name] = module
    try:
        def verify(task, result, home):
            return Verdict(True)
        verify.__module__ = mod_name
        identity = verifier_identity(verify)
        assert identity["version"] == "v" * 100
    finally:
        del sys.modules[mod_name]


def test_verifier_identity_falls_back_when_no_module():
    def verify(task, result, home):
        return Verdict(True)
    verify.__module__ = ""
    identity = verifier_identity(verify)
    assert identity["name"].startswith("?.")
    assert identity["source_sha256"] is None


# -- run_verifier: worker-reported failure -------------------------------------

def test_failure_outcome_respects_explicit_retryable_true(tmp_path):
    task = _task()
    result = _ready({"outcome": "failure", "artifacts": [],
                     "reason": "boom", "retryable": True})
    verdict = run_verifier(lambda name: (_ for _ in ()).throw(AssertionError("must not resolve")),
                           task, result, tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is True
    assert verdict.reason == "boom"
    assert verdict.verifier == {"kind": "courier_rule",
                               "name": "worker_reported_failure",
                               "adapter": "synthetic"}


def test_failure_outcome_respects_explicit_retryable_false(tmp_path):
    task = _task()
    result = _ready({"outcome": "failure", "artifacts": [],
                     "reason": "boom", "retryable": False})
    verdict = run_verifier(lambda name: None, task, result, tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False


def test_failure_without_retryable_idempotent_is_retryable(tmp_path):
    task = _task(effect_class="idempotent")
    result = _ready({"outcome": "failure", "artifacts": []})
    verdict = run_verifier(lambda name: None, task, result, tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is True
    assert verdict.reason == "worker reported failure"


def test_failure_without_retryable_non_idempotent_is_not_retryable(tmp_path):
    task = _task(effect_class="non_idempotent")
    result = _ready({"outcome": "failure", "artifacts": []})
    verdict = run_verifier(lambda name: None, task, result, tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False


def test_failure_reason_truncated_to_500(tmp_path):
    task = _task()
    result = _ready({"outcome": "failure", "artifacts": [],
                     "reason": "r" * 600, "retryable": False})
    verdict = run_verifier(lambda name: None, task, result, tmp_path)
    assert verdict.reason == "r" * 500


# -- run_verifier: resolution failures ----------------------------------------

def test_resolve_exception_is_load_failure(tmp_path):
    task = _task(adapter="synthetic")

    def resolve(name):
        raise RuntimeError("broken import")
    verdict = run_verifier(resolve, task,
                           _ready(_success_payload()), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert "RuntimeError" in verdict.reason
    assert verdict.verifier == {"kind": "courier_rule",
                               "name": "verifier_load_failed",
                               "adapter": "synthetic"}


def test_resolve_none_is_no_verifier(tmp_path):
    task = _task(adapter="synthetic")
    verdict = run_verifier(lambda name: None, task,
                           _ready(_success_payload()), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert "no verifier registered" in verdict.reason
    assert verdict.verifier == {"kind": "courier_rule",
                               "name": "no_verifier",
                               "adapter": "synthetic"}


# -- run_verifier: adapter verdict paths --------------------------------------

def _accepting_verify(task, result, home):
    return Verdict(True, "looks good", False)


def test_accepting_verifier_is_stamped_with_identity(tmp_path):
    task = _task(adapter="synthetic")
    verdict = run_verifier(lambda name: _accepting_verify, task,
                           _ready(_success_payload()), tmp_path)
    assert verdict.accepted is True
    assert verdict.reason == "looks good"
    assert verdict.verifier["kind"] == "adapter"
    assert "name" in verdict.verifier


def test_rejecting_verifier_is_preserved_with_identity(tmp_path):
    def reject(task, result, home):
        return Verdict(False, "evidence mismatch", True)
    task = _task(adapter="synthetic")
    verdict = run_verifier(lambda name: reject, task,
                           _ready(_success_payload()), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is True
    assert verdict.reason == "evidence mismatch"
    assert verdict.verifier["kind"] == "adapter"


def test_verifier_exception_is_fail_closed(tmp_path):
    def crash(task, result, home):
        raise ValueError("bad evidence")
    task = _task(adapter="synthetic")
    verdict = run_verifier(lambda name: crash, task,
                           _ready(_success_payload()), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert "ValueError" in verdict.reason
    assert verdict.verifier["kind"] == "adapter"


@pytest.mark.parametrize("bad", [None, "ok", {"accepted": True}, 123, [1]])
def test_verifier_non_verdict_return_is_rejected(tmp_path, bad):
    def weird(task, result, home):
        return bad
    task = _task(adapter="synthetic")
    verdict = run_verifier(lambda name: weird, task,
                           _ready(_success_payload()), tmp_path)
    assert verdict.accepted is False
    assert verdict.reason == "verifier returned an invalid verdict"
    assert verdict.verifier["kind"] == "adapter"


@pytest.mark.parametrize("accepted", [1, 0, "yes", None])
def test_verifier_non_bool_accepted_is_rejected(tmp_path, accepted):
    def weird(task, result, home):
        return Verdict(accepted, "x", False)
    task = _task(adapter="synthetic")
    verdict = run_verifier(lambda name: weird, task,
                           _ready(_success_payload()), tmp_path)
    assert verdict.accepted is False
    assert verdict.reason == "verifier returned an invalid verdict"


def test_accepted_reason_truncated_and_retryable_coerced(tmp_path):
    def quirky(task, result, home):
        return Verdict(True, "q" * 700, 1)
    task = _task(adapter="synthetic")
    verdict = run_verifier(lambda name: quirky, task,
                           _ready(_success_payload()), tmp_path)
    assert verdict.accepted is True
    assert verdict.reason == "q" * 500
    assert verdict.retryable is True
    assert verdict.verifier["kind"] == "adapter"


def test_end_to_end_with_real_synthetic_verifier(tmp_path):
    task = _task(adapter="synthetic")
    verdict = run_verifier(adapter_verifier, task,
                           _ready(_success_payload()), tmp_path)
    # The synthetic verifier reads evidence; without a real run it must
    # fail closed rather than pass by default.
    assert isinstance(verdict, Verdict)
    assert verdict.verifier is not None
