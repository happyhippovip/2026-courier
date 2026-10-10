"""P9 test hardening for courier_worker.adapter_bridge (effect-key + params bounds).

Tests only; no behavior change. Pins validate_request() fail-closed edges:
effect_key shape (allowed charset, length 1..200) and params JSON/size
guards (plain-JSON only, 64 KiB bound) plus spec-shape rejections. No
network, no credentials, no filesystem writes.
"""

import json

import pytest

from courier_worker import adapter_bridge as A
from courier_worker.host import SpecError


def _spec(**over):
    base = {"adapter": "synthetic", "params": {}, "effect_key": "k1"}
    base.update(over)
    return base


def test_effect_key_minimal_and_charset_ok():
    adapter, params, key = A.validate_request(_spec(effect_key="a"))
    assert (adapter, key) == ("synthetic", "a")
    assert params == {}
    adapter, _, key = A.validate_request(_spec(effect_key="Ab_9.:-Z"))
    assert key == "Ab_9.:-Z"


def test_effect_key_max_length_ok():
    key = "k" * 200
    _, _, out = A.validate_request(_spec(effect_key=key))
    assert out == key


def test_effect_key_too_long_rejected():
    with pytest.raises(SpecError, match="effect_key"):
        A.validate_request(_spec(effect_key="k" * 201))


@pytest.mark.parametrize("bad", [
    "has space",
    "semi;colon",
    "slash/x",
    "back\\slash",
    "at@sign",
    "hash#tag",
    "line\nbreak",
    "caf\u00e9",
    "emoji-\U0001f600",
    "",
])
def test_effect_key_bad_charset_rejected(bad):
    with pytest.raises(SpecError, match="effect_key"):
        A.validate_request(_spec(effect_key=bad))


@pytest.mark.parametrize("bad", [None, 123, True, ["k1"], {"k": "k1"}])
def test_effect_key_non_string_rejected(bad):
    with pytest.raises(SpecError, match="effect_key"):
        A.validate_request(_spec(effect_key=bad))


def test_effect_key_missing_rejected():
    spec = {"adapter": "synthetic", "params": {}}
    with pytest.raises(SpecError, match="effect_key"):
        A.validate_request(spec)


@pytest.mark.parametrize("spec", [None, [], "x", 42])
def test_spec_not_object_rejected(spec):
    with pytest.raises(SpecError, match="no spec object"):
        A.validate_request(spec)


def test_spec_with_argv_rejected():
    with pytest.raises(SpecError, match="must not carry argv"):
        A.validate_request(_spec(argv=["anything"]))


@pytest.mark.parametrize("adapter", ["shell", "os", "courier_worker.adapter_runner", None, 7, True])
def test_unknown_adapter_rejected(adapter):
    with pytest.raises(SpecError, match="not allowlisted"):
        A.validate_request(_spec(adapter=adapter))


@pytest.mark.parametrize("params", ["sleep 1", ["a"], None, 5])
def test_params_not_object_rejected(params):
    with pytest.raises(SpecError, match="params must be an object"):
        A.validate_request(_spec(params=params))


def test_params_non_finite_rejected():
    with pytest.raises(SpecError, match="not plain JSON"):
        A.validate_request(_spec(params={"sleep_s": float("nan")}))
    with pytest.raises(SpecError, match="not plain JSON"):
        A.validate_request(_spec(params={"sleep_s": float("inf")}))


def test_params_not_plain_json_rejected():
    with pytest.raises(SpecError, match="not plain JSON"):
        A.validate_request(_spec(params={"content": {"nested": {1, 2}}}))
    with pytest.raises(SpecError, match="not plain JSON"):
        A.validate_request(_spec(params={"content": b"bytes"}))


def test_params_over_size_bound_rejected():
    big = {"content": "x" * (70 * 1024)}
    encoded = json.dumps(big, sort_keys=True, allow_nan=False)
    assert len(encoded.encode("utf-8")) > A.MAX_PARAMS_BYTES
    with pytest.raises(SpecError, match="size bound"):
        A.validate_request(_spec(params=big))


def test_params_under_size_bound_accepted():
    params = {"content": "y" * 1024}
    adapter, out_params, key = A.validate_request(_spec(params=params))
    assert adapter == "synthetic" and key == "k1"
    assert out_params == params
