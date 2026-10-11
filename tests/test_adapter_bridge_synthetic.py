"""[L4][P9-adapter_bridge_synthetic] synthetic-adapter delegation pins.

Tests only; no behavior change. Pins how ``courier_worker.adapter_bridge``
delegates ``"synthetic"`` claims to the trusted ``adapters.synthetic``
validator: valid params pass through, param errors and a missing adapter
implementation both fail closed as :class:`SpecError` (never a leaked
``SyntheticError``/``ImportError``, never a run of unvalidated params).
No network, no subprocesses, no files outside pytest's tmp handling
(none needed: ``validate_request`` is pure).
"""

import sys

import pytest

from courier_worker import adapter_bridge
from courier_worker.host import SpecError


def _spec(**changes):
    value = {"adapter": "synthetic", "params": {}, "effect_key": "eff-1"}
    value.update(changes)
    return value


def test_registry_lists_only_synthetic():
    assert set(adapter_bridge.ADAPTERS) == {"synthetic"}


def test_valid_synthetic_params_pass_through():
    params = {"write": "out.txt", "content": "hello"}
    adapter, out_params, effect_key = adapter_bridge.validate_request(_spec(params=params))
    assert adapter == "synthetic"
    assert out_params == params
    assert effect_key == "eff-1"


def test_empty_params_use_adapter_defaults_and_pass():
    adapter, out_params, _ = adapter_bridge.validate_request(_spec())
    assert adapter == "synthetic"
    assert out_params == {}


@pytest.mark.parametrize("params", [
    {"sleep_s": -1},
    {"hang": "yes"},
    {"fault_attempts": []},
    {"fault_attempts": [0]},
    {"fail_transient_n": -2},
    {"write": "../escape.txt"},
    {"content": 123},
    {"crash_after_s": "soon"},
])
def test_invalid_synthetic_params_fail_closed_as_spec_error(params):
    with pytest.raises(SpecError) as excinfo:
        adapter_bridge.validate_request(_spec(params=params))
    assert str(excinfo.value).startswith("synthetic params rejected: ")


def test_param_rejection_carries_underlying_reason():
    with pytest.raises(SpecError) as excinfo:
        adapter_bridge.validate_request(_spec(params={"sleep_s": -1}))
    assert str(excinfo.value) == (
        "synthetic params rejected: sleep_s must be a non-negative number")


def test_param_error_does_not_leak_raw_synthetic_error():
    try:
        adapter_bridge.validate_request(_spec(params={"hang": "yes"}))
    except SpecError:
        pass
    except ValueError:
        pytest.fail("raw SyntheticError leaked instead of SpecError")
    else:
        pytest.fail("invalid synthetic params were accepted")


def test_unknown_adapter_is_not_delegated():
    with pytest.raises(SpecError, match="not allowlisted"):
        adapter_bridge.validate_request(_spec(adapter="nope"))


def test_missing_adapter_implementation_fails_closed(monkeypatch):
    monkeypatch.setitem(sys.modules, "adapters", None)
    with pytest.raises(SpecError, match="adapter implementation unavailable"):
        adapter_bridge.validate_request(_spec())
