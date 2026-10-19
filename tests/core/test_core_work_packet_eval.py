"""P9-work_packet_eval: evaluate_packet + PacketQueue edge pins for courier_core.work_packet.

Tests only; no behavior change. Offline, no network, no credentials.
Covers identity/field-preservation and queue-ordering edges not pinned by
tests/core/test_work_packet.py at the base commit.
"""

from dataclasses import FrozenInstanceError

import pytest

from courier_core.work_packet import PacketQueue, PacketState, WorkPacket, evaluate_packet


def _packet(pid="p1", owner="w1", sha="sha1", state=PacketState.CURRENT):
    return WorkPacket(id=pid, owner_id=owner, target_sha=sha, state=state)


def test_packet_state_values_are_stable_strings():
    assert [s.value for s in PacketState] == [
        "CURRENT", "NEXT", "AFTER_NEXT", "WAITING_FOR_EVIDENCE", "SUPERSEDED", "PARKED_BY_HOST",
    ]
    assert len({s.value for s in PacketState}) == len(PacketState)


def test_evaluate_returns_identical_object_when_nothing_changes():
    packet = _packet(state=PacketState.CURRENT)
    assert evaluate_packet(packet, current_sha="sha1", host_safe=True) is packet


def test_evaluate_does_not_promote_next_by_itself():
    packet = _packet(state=PacketState.NEXT)
    evaluated = evaluate_packet(packet, current_sha="sha1", host_safe=True)
    assert evaluated is packet
    assert evaluated.state == PacketState.NEXT


def test_evaluate_leaves_after_next_and_waiting_untouched_when_safe():
    for state in (PacketState.AFTER_NEXT, PacketState.WAITING_FOR_EVIDENCE):
        packet = _packet(state=state)
        assert evaluate_packet(packet, current_sha="sha1", host_safe=True) is packet


def test_superseded_early_return_keeps_identical_object_even_when_stale_and_unsafe():
    packet = _packet(state=PacketState.SUPERSEDED, sha="sha-old")
    evaluated = evaluate_packet(packet, current_sha="sha-new", host_safe=False)
    assert evaluated is packet
    assert evaluated.state == PacketState.SUPERSEDED


def test_transitions_preserve_identity_fields():
    parked = evaluate_packet(_packet(pid="p", owner="w", sha="s"), current_sha="s", host_safe=False)
    assert (parked.id, parked.owner_id, parked.target_sha) == ("p", "w", "s")
    superseded = evaluate_packet(_packet(pid="p", owner="w", sha="s"), current_sha="other", host_safe=False)
    assert (superseded.id, superseded.owner_id, superseded.target_sha) == ("p", "w", "s")
    assert superseded.state == PacketState.SUPERSEDED
    woken = evaluate_packet(_packet(state=PacketState.PARKED_BY_HOST), current_sha="sha1", host_safe=True)
    assert (woken.id, woken.owner_id, woken.target_sha) == ("p1", "w1", "sha1")
    assert woken.state == PacketState.CURRENT


def test_waiting_for_evidence_is_parked_when_host_unsafe():
    evaluated = evaluate_packet(
        _packet(state=PacketState.WAITING_FOR_EVIDENCE), current_sha="sha1", host_safe=False)
    assert evaluated.state == PacketState.PARKED_BY_HOST
    assert (evaluated.id, evaluated.owner_id, evaluated.target_sha) == ("p1", "w1", "sha1")


def test_work_packet_equality_is_by_value():
    assert _packet() == _packet()
    assert _packet(pid="a") != _packet(pid="b")
    with pytest.raises(FrozenInstanceError):
        _packet().state = PacketState.SUPERSEDED


def test_add_packet_overwrites_same_id():
    queue = PacketQueue()
    queue.add_packet(_packet(pid="p", owner="w1", state=PacketState.NEXT))
    queue.add_packet(_packet(pid="p", owner="w2", state=PacketState.NEXT))
    assert queue.packets["p"].owner_id == "w2"


def test_first_current_in_insertion_order_wins():
    queue = PacketQueue()
    queue.add_packet(_packet(pid="first", state=PacketState.CURRENT))
    queue.add_packet(_packet(pid="second", state=PacketState.CURRENT))
    admissible = queue.get_admissible_packet("sha1", host_safe=True)
    assert admissible is not None and admissible.id == "first"


def test_promotion_is_stored_in_the_queue():
    queue = PacketQueue()
    queue.add_packet(_packet(pid="n", state=PacketState.NEXT))
    admissible = queue.get_admissible_packet("sha1", host_safe=True)
    assert admissible is not None and admissible.state == PacketState.CURRENT
    assert queue.packets["n"].state == PacketState.CURRENT
    assert queue.packets["n"] == admissible


def test_stale_next_is_superseded_not_promoted():
    queue = PacketQueue()
    queue.add_packet(WorkPacket("n", "w", "sha-old", PacketState.NEXT))
    assert queue.get_admissible_packet("sha-new", host_safe=True) is None
    assert queue.packets["n"].state == PacketState.SUPERSEDED


def test_only_superseded_packets_yield_none():
    queue = PacketQueue()
    queue.add_packet(_packet(pid="s", state=PacketState.SUPERSEDED))
    assert queue.get_admissible_packet("sha1", host_safe=True) is None


def test_unsafe_host_reparks_current_and_yields_none():
    queue = PacketQueue()
    queue.add_packet(_packet(pid="c", state=PacketState.CURRENT))
    assert queue.get_admissible_packet("sha1", host_safe=False) is None
    assert queue.packets["c"].state == PacketState.PARKED_BY_HOST
