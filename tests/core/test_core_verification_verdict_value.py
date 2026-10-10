"""P9 test hardening for courier_core.verification (Verdict value-object pins).

Tests only; no behavior change. The open run_verifier / verifier-identity
pins cover the fail-closed rules around adapters; none of them pins the
Verdict value semantics themselves, so this file pins exactly that: the
verdict is an immutable, hashable value object with equality by value, and
dataclasses.replace() (the exact operation run_verifier uses to stamp the
verifier identity) preserves the type while leaving the original untouched.
No network, no credentials, no filesystem writes.
"""

import dataclasses

import pytest

from courier_core.verification import Verdict


def _verdict(**overrides):
    fields = {"accepted": True, "reason": "ok", "retryable": False,
              "verifier": {"kind": "courier_rule", "name": "probe", "adapter": "synthetic"}}
    fields.update(overrides)
    return Verdict(**fields)


def test_verdict_fields_are_exactly_the_documented_four():
    assert [f.name for f in dataclasses.fields(Verdict)] == [
        "accepted", "reason", "retryable", "verifier"]


def test_verdict_is_frozen():
    verdict = _verdict()
    with pytest.raises(dataclasses.FrozenInstanceError):
        verdict.reason = "mutated"  # type: ignore[misc]
    assert verdict.reason == "ok"


def test_verdict_equality_is_by_value():
    assert _verdict() == _verdict()
    assert _verdict() != _verdict(reason="different")
    assert _verdict() != _verdict(accepted=False)
    assert _verdict() != _verdict(retryable=True)
    assert _verdict() != _verdict(verifier=None)
    assert _verdict() != "not-a-verdict"


def test_verdict_hash_matches_equality_when_fields_hashable():
    assert hash(_verdict(verifier=None)) == hash(_verdict(verifier=None))
    assert len({_verdict(verifier=None), _verdict(verifier=None),
                _verdict(reason="other", verifier=None)}) == 2


def test_verdict_with_dict_verifier_is_unhashable():
    with pytest.raises(TypeError):
        hash(_verdict())


def test_replace_stamps_overrides_and_preserves_type():
    verdict = _verdict()
    stamped = dataclasses.replace(
        verdict, reason="x" * 600, retryable=True,
        verifier={"kind": "adapter", "name": "m.v", "version": None, "source_sha256": None})
    assert type(stamped) is Verdict
    assert stamped.accepted is True
    assert stamped.reason == "x" * 600
    assert stamped.retryable is True
    assert stamped.verifier == {"kind": "adapter", "name": "m.v", "version": None,
                                "source_sha256": None}


def test_replace_leaves_original_untouched():
    verdict = _verdict()
    dataclasses.replace(verdict, reason="changed", retryable=True, verifier=None)
    assert verdict == _verdict()
