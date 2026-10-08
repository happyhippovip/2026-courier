import pytest
from courier_core.work_packet import (
    PacketQueue,
    PacketState,
    WorkPacket,
    evaluate_packet,
)


def test_evaluate_packet_matching_sha_and_safe_host():
    pkt = WorkPacket(id="p-1", owner_id="mac-worker", target_sha="sha-100", state=PacketState.CURRENT)
    evaluated = evaluate_packet(pkt, current_sha="sha-100", host_safe=True)
    assert evaluated.state == PacketState.CURRENT
    assert evaluated == pkt


def test_evaluate_packet_mismatched_sha_supersedes():
    pkt = WorkPacket(id="p-1", owner_id="mac-worker", target_sha="sha-100", state=PacketState.CURRENT)
    evaluated = evaluate_packet(pkt, current_sha="sha-200", host_safe=True)
    assert evaluated.state == PacketState.SUPERSEDED
    assert evaluated.id == "p-1"

    # Once superseded, it stays superseded
    re_evaluated = evaluate_packet(evaluated, current_sha="sha-100", host_safe=True)
    assert re_evaluated.state == PacketState.SUPERSEDED


def test_evaluate_packet_host_unsafe_parks_and_unparks():
    pkt = WorkPacket(id="p-1", owner_id="mac-worker", target_sha="sha-100", state=PacketState.CURRENT)
    parked = evaluate_packet(pkt, current_sha="sha-100", host_safe=False)
    assert parked.state == PacketState.PARKED_BY_HOST

    # Unpark when host becomes safe
    unparked = evaluate_packet(parked, current_sha="sha-100", host_safe=True)
    assert unparked.state == PacketState.CURRENT


def test_packet_queue_one_writer_lock():
    q = PacketQueue()
    p1 = WorkPacket(id="p-1", owner_id="writer-1", target_sha="sha-main", state=PacketState.CURRENT)
    p2 = WorkPacket(id="p-2", owner_id="writer-2", target_sha="sha-main", state=PacketState.NEXT)
    q.add_packet(p1)
    q.add_packet(p2)

    # When p1 is CURRENT, it retains lock; p2 is not promoted
    admissible = q.get_admissible_packet(current_sha="sha-main", host_safe=True)
    assert admissible is not None
    assert admissible.id == "p-1"
    assert admissible.state == PacketState.CURRENT
    assert q.packets["p-2"].state == PacketState.NEXT


def test_packet_queue_promotes_next_when_no_current():
    q = PacketQueue()
    p1 = WorkPacket(id="p-1", owner_id="writer-1", target_sha="sha-main", state=PacketState.NEXT)
    q.add_packet(p1)

    admissible = q.get_admissible_packet(current_sha="sha-main", host_safe=True)
    assert admissible is not None
    assert admissible.id == "p-1"
    assert admissible.state == PacketState.CURRENT
    assert q.packets["p-1"].state == PacketState.CURRENT


def test_packet_queue_blocked_when_host_unsafe():
    q = PacketQueue()
    p1 = WorkPacket(id="p-1", owner_id="writer-1", target_sha="sha-main", state=PacketState.NEXT)
    q.add_packet(p1)

    admissible = q.get_admissible_packet(current_sha="sha-main", host_safe=False)
    assert admissible is None
    # Cannot promote when host is unsafe
    assert q.packets["p-1"].state != PacketState.CURRENT
