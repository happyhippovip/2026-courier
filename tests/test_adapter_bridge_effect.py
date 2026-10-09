"""P9 hardening for courier_worker.adapter_bridge: effect-envelope pins.

Tests only; no behavior change. Focused slice on the claim ``spec`` effect
envelope (``adapter`` allowlist gate, ``params`` JSON/size/validator shape,
``effect_key`` format, and the ``argv`` refusal), independent of the other
open P9 adapter_bridge PRs which use separate filenames
(``test_adapter_bridge*.py`` variants cover paths/round-trip/unicode).

No network, no subprocesses, no credentials. Filesystem use is limited to
in-memory dicts (no tmp files needed for this slice).
"""

from __future__ import annotations

import json
import math

import pytest

from courier_worker import adapter_bridge
from courier_worker.adapter_bridge import (
    ADAPTERS,
    EFFECT_KEY_RE,
    MAX_PARAMS_BYTES,
    REPORT_OUTCOMES,
    validate_request,
)
from courier_worker.host import SpecError


def _spec(**overrides):
    base = {"adapter": "synthetic", "params": {}, "effect_key": "eff-1"}
    base.update(overrides)
    return base


# -- module constants --------------------------------------------------------


def test_adapters_registry_is_closed_to_synthetic():
    assert set(ADAPTERS.keys()) == {"synthetic"}
    assert callable(ADAPTERS["synthetic"])


def test_max_params_bytes_is_64kib():
    assert MAX_PARAMS_BYTES == 64 * 1024


def test_report_outcomes_are_success_and_failure_only():
    assert REPORT_OUTCOMES == frozenset({"success", "failure"})


def test_effect_key_regex_accepts_boundaries():
    assert EFFECT_KEY_RE.match("a")
    assert EFFECT_KEY_RE.match("A-9_.:-z")
    assert EFFECT_KEY_RE.match("x" * 200)
    assert EFFECT_KEY_RE.match("eff-1.0:test_key")


def test_effect_key_regex_rejects_bad_shapes():
    assert not EFFECT_KEY_RE.match("")
    assert not EFFECT_KEY_RE.match("x" * 201)
    assert not EFFECT_KEY_RE.match("has space")
    assert not EFFECT_KEY_RE.match("has/slash")
    assert not EFFECT_KEY_RE.match("caf\u00e9")


# -- validate_request: structural refusal --------------------------------------


@pytest.mark.parametrize("bad", [None, [], "spec", 42, True])
def test_rejects_non_dict_spec(bad):
    with pytest.raises(SpecError):
        validate_request(bad)


@pytest.mark.parametrize("argv", [None, [], ["x"], "cmd", 0, False])
def test_rejects_spec_carrying_argv(argv):
    with pytest.raises(SpecError):
        validate_request(_spec(argv=argv))


@pytest.mark.parametrize("bad", [None, "", 42, "SYNTHETIC", "local_shell", "synthetic "])
def test_rejects_unknown_or_non_string_adapter(bad):
    with pytest.raises(SpecError):
        validate_request(_spec(adapter=bad))


def test_rejects_missing_adapter_key():
    spec = {"params": {}, "effect_key": "eff-1"}
    with pytest.raises(SpecError):
        validate_request(spec)


@pytest.mark.parametrize("bad", [None, [], "params", 42, True])
def test_rejects_non_dict_params(bad):
    with pytest.raises(SpecError):
        validate_request(_spec(params=bad))


def test_rejects_nan_and_inf_params():
    with pytest.raises(SpecError):
        validate_request(_spec(params={"sleep_s": float("nan")}))
    with pytest.raises(SpecError):
        validate_request(_spec(params={"sleep_s": float("inf")}))
    assert math.isnan(float("nan"))  # sanity: the fixture really is non-JSON


def test_rejects_non_serializable_params():
    with pytest.raises(SpecError):
        validate_request(_spec(params={"write": {"as", "set"}}))


def test_rejects_oversize_params():
    big = {"content": "x" * (MAX_PARAMS_BYTES + 1024)}
    assert len(json.dumps(big).encode("utf-8")) > MAX_PARAMS_BYTES
    with pytest.raises(SpecError):
        validate_request(_spec(params=big))


def test_accepts_params_near_but_within_bound():
    # 60 KiB of content stays under the 64 KiB envelope (keys add ~15 bytes).
    content = "y" * (60 * 1024)
    params = {"content": content}
    assert len(json.dumps(params).encode("utf-8")) < MAX_PARAMS_BYTES
    adapter, out_params, effect_key = validate_request(_spec(params=params))
    assert adapter == "synthetic"
    assert out_params == params
    assert effect_key == "eff-1"


def test_rejects_params_refused_by_adapter_validator():
    with pytest.raises(SpecError):
        validate_request(_spec(params={"write": "../evil.txt"}))


# -- validate_request: effect_key ----------------------------------------------


@pytest.mark.parametrize("bad", [None, "", 42, True, "has space", "a/b", "x" * 201])
def test_rejects_missing_or_malformed_effect_key(bad):
    with pytest.raises(SpecError):
        validate_request(_spec(effect_key=bad))


def test_rejects_missing_effect_key_entirely():
    spec = {"adapter": "synthetic", "params": {}}
    with pytest.raises(SpecError):
        validate_request(spec)


def test_accepts_effect_key_boundaries():
    for key in ("k", "x" * 200, "A-9_.:-z", "eff-1.0:test_key"):
        adapter, _, out_key = validate_request(_spec(effect_key=key))
        assert adapter == "synthetic"
        assert out_key == key


# -- validate_request: happy path ----------------------------------------------


def test_accepts_minimal_valid_spec():
    adapter, params, effect_key = validate_request(_spec())
    assert adapter == "synthetic"
    assert params == {}
    assert effect_key == "eff-1"


def test_happy_path_returns_params_object_and_key_verbatim():
    params = {"content": "hello", "write": "out.txt"}
    adapter, out_params, out_key = validate_request(
        _spec(params=params, effect_key="dispatch-42:attempt-1")
    )
    assert adapter == "synthetic"
    assert out_params == params
    assert out_key == "dispatch-42:attempt-1"


def test_module_exposes_spec_error():
    assert adapter_bridge.SpecError is SpecError
