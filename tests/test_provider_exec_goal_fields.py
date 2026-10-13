"""provider_exec accepts the bridge's goal binding (goal_id, goal_fingerprint)
and still rejects every other unknown key. Includes a MOCK-provider A->B run
with goal binding through the real worker path (no model, no cost; not a
Gate 3 pass)."""

import pytest

import tests.test_gate3_mock_provider_ab as gate3
from courier_worker.adapters.provider_exec import ProviderExecError, build_argv, validate

GOAL_ID = "goal.gate3.mock"
GOAL_FP = "a" * 64


def _params(**extra):
    return {"provider": "muse", "prompt": "say A", "timeout_s": 60, **extra}


def test_goal_fields_are_accepted_and_never_reach_argv():
    spec = validate(_params(goal_id=GOAL_ID, goal_fingerprint=GOAL_FP))
    assert "goal_id" not in spec and "goal_fingerprint" not in spec
    argv = build_argv("/bin/true", "/tmp/p.txt", spec)
    assert not any(GOAL_ID in a or GOAL_FP in a for a in argv)


def test_agy_accepts_goal_fields_too():
    spec = validate({"provider": "agy", "prompt": "say A", "goal_id": GOAL_ID, "goal_fingerprint": GOAL_FP})
    assert "goal_id" not in spec


@pytest.mark.parametrize("extra,code", [
    ({"goal_id": GOAL_ID}, "BAD_GOAL"),
    ({"goal_fingerprint": GOAL_FP}, "BAD_GOAL"),
    ({"goal_id": "bad id", "goal_fingerprint": GOAL_FP}, "BAD_GOAL"),
    ({"goal_id": GOAL_ID, "goal_fingerprint": 7}, "BAD_GOAL"),
    ({"goal_id": "g" * 129, "goal_fingerprint": GOAL_FP}, "BAD_GOAL"),
    ({"goal_id": GOAL_ID, "goal_fingerprint": GOAL_FP, "workspace": "x"}, "UNKNOWN_KEY"),
    ({"goal": GOAL_ID}, "UNKNOWN_KEY"),
    ({"inputs": []}, "UNKNOWN_KEY"),
])
def test_bad_goal_or_other_unknown_keys_are_rejected(extra, code):
    with pytest.raises(ProviderExecError) as err:
        validate(_params(**extra))
    assert err.value.reason_code == code


def test_mock_provider_a_then_b_with_goal_binding(tmp_path, monkeypatch):
    original = gate3._spec

    def goal_spec(prompt):
        spec = original(prompt)
        spec.update(goal_id=GOAL_ID, goal_fingerprint=GOAL_FP)   # bridge copies these into params
        return spec

    monkeypatch.setattr(gate3, "_spec", goal_spec)
    gate3.test_mock_provider_a_then_b_zero_human_relay(tmp_path, monkeypatch)
    import json
    missions = json.loads((tmp_path / "home" / "ledger_bridge_state.json").read_text())["missions"]
    assert all(m.get("goal_id") == GOAL_ID and m.get("goal_fingerprint") == GOAL_FP for m in missions.values())
