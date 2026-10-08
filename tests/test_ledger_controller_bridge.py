"""Ledger -> controller bridge: one-shot idempotent mint + fail-closed receipts.

NOT RUN ON THIS HOST (swap-critical): committed as the regression contract;
CI (ubuntu + windows pytest) is the execution venue. Each test names the
exact bridge guarantee it pins.
"""

import pytest

from scripts.ledger_controller_bridge import (
    BridgeRefused,
    eligible_for_mint,
    idempotency_key,
    mint_packet,
    next_eligible,
    receipt_event_fields,
)

OWNER = "MUSE_MAC"
OTHER = "GOOGLE_WINDOWS"


def _mission(mission_id, status="WORKING", owner=OWNER, depends_on=()):
    return {
        "mission_id": mission_id,
        "agent_id": owner,
        "host_id": "MAC_LOCAL",
        "status": status,
        "depends_on": list(depends_on),
        "ownership": owner,
    }


def _done(mission_id):
    return _mission(mission_id, status="DONE", owner=OTHER)


def test_eligible_only_when_working_owned_and_deps_done():
    missions = {"a": _mission("a"), "b": _mission("b", depends_on=["a"]), "a2": _done("a2")}
    ok, reason = eligible_for_mint(missions["b"], {"a": _done("a"), "b": missions["b"]}, OWNER)
    assert (ok, reason) == (True, "ELIGIBLE")
    blocked, why = eligible_for_mint(missions["b"], missions, OWNER)
    assert blocked is False and why == "DEPENDENCY_NOT_DONE:a"


def test_foreign_owned_and_non_working_missions_refused():
    missions = {"mine": _mission("mine"), "theirs": _mission("theirs", owner=OTHER),
                "done": _done("done")}
    assert eligible_for_mint(missions["theirs"], missions, OWNER) == (False, "NOT_OWNER")
    assert eligible_for_mint(missions["done"], missions, OWNER)[0] is False


def test_mint_packet_keys_idempotency_and_passes_caller_spec_through():
    missions = {"a": _done("a"), "b": _mission("b", depends_on=["a"])}
    first = mint_packet(missions["b"], missions, owner=OWNER, mint_event_id="mint-1",
                        adapter="synthetic", params={"p": 1},
                        effect_class="none", lease_ttl_s=60)
    assert first["adapter"] == "synthetic"
    assert first["params"] == {"p": 1}
    assert first["idempotency_key"] == "ledger:b:mint-1"
    again = mint_packet(missions["b"], missions, owner=OWNER, mint_event_id="mint-1",
                        adapter="synthetic", params={"p": 1},
                        effect_class="none", lease_ttl_s=60)
    assert again["idempotency_key"] == first["idempotency_key"]
    other = mint_packet(missions["b"], missions, owner=OWNER, mint_event_id="mint-2",
                        adapter="synthetic", params={"p": 1},
                        effect_class="none", lease_ttl_s=60)
    assert other["idempotency_key"] != first["idempotency_key"]


def test_mint_refuses_bad_spec_and_ineligible_mission():
    missions = {"a": _mission("a"), "b": _mission("b", depends_on=["a"])}
    with pytest.raises(BridgeRefused):
        mint_packet(missions["b"], missions, owner=OWNER, mint_event_id="m",
                    adapter="synthetic", params={"p": 1},
                    effect_class="none", lease_ttl_s=60)  # dep a not DONE
    with pytest.raises(BridgeRefused):
        mint_packet(missions["a"], missions, owner=OWNER, mint_event_id="m",
                    adapter="", params={}, effect_class="none", lease_ttl_s=60)
    with pytest.raises(BridgeRefused):
        idempotency_key("", "m")


def test_receipt_verified_complete_is_final_and_releases():
    mission = _mission("b", depends_on=["a"])
    fields = receipt_event_fields(
        mission, event_id="evt-1", created_at="2026-10-08T08:00:00+00:00",
        controller_record={"task_id": "task-abc", "duplicate": False,
                           "controller_status": 200, "verified": True,
                           "outcome": "COMPLETE", "result_id": "res-1",
                           "source_sha": "f425d328"})
    assert (fields["event_type"], fields["status"]) == ("FINAL", "DONE")
    assert fields["evidence_ref"] == "controller:task-abc:res-1"
    assert fields["mission_id"] == "b"


def test_receipt_never_turns_failure_into_done():
    mission = _mission("b")
    failed = receipt_event_fields(
        mission, event_id="evt-2", created_at="2026-10-08T08:00:00+00:00",
        controller_record={"task_id": "task-abc", "duplicate": False,
                           "controller_status": 200, "verified": False,
                           "outcome": "FAILED", "result_id": "res-1",
                           "source_sha": "f425d328"})
    assert (failed["event_type"], failed["status"]) == ("BLOCKED", "BLOCKED")
    blocked = receipt_event_fields(
        mission, event_id="evt-3", created_at="2026-10-08T08:00:00+00:00",
        controller_record={"task_id": "task-abc", "duplicate": True,
                           "controller_status": 200, "verified": True,
                           "outcome": "BLOCKED", "result_id": "res-1",
                           "source_sha": "f425d328"})
    assert (blocked["event_type"], blocked["status"]) == ("BLOCKED", "BLOCKED")
    with pytest.raises(BridgeRefused):
        receipt_event_fields(
            mission, event_id="evt-4", created_at="2026-10-08T08:00:00+00:00",
            controller_record={"task_id": "task-abc", "verified": True,
                               "outcome": "SOMETHING_ELSE", "source_sha": "f425d328"})
    verified_failed = receipt_event_fields(
        mission, event_id="evt-5", created_at="2026-10-08T08:00:00+00:00",
        controller_record={"task_id": "task-abc", "duplicate": False,
                           "controller_status": 200, "verified": True,
                           "outcome": "FAILED", "result_id": "res-1",
                           "source_sha": "f425d328"})
    assert (verified_failed["event_type"], verified_failed["status"]) == ("ERROR", "ERROR")


def test_next_eligible_returns_distinct_ready_missions_in_order():
    missions = {
        "b": _mission("b", depends_on=["a"]),
        "a": _done("a"),
        "c": _mission("c"),
        "d": _mission("d", owner=OTHER),
        "e": _mission("e", status="BLOCKED"),
    }
    assert next_eligible(missions, OWNER) == ["b", "c"]
