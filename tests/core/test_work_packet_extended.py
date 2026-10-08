from dataclasses import FrozenInstanceError
import pytest
from courier_core.work_packet import (
    PacketQueue,
    PacketState,
    WorkPacket,
    evaluate_packet,
)

def test_work_packet_immutability():
    packet = WorkPacket(id="p-imm", owner_id="writer-alpha", target_sha="sha-init", state=PacketState.CURRENT)
    with pytest.raises(FrozenInstanceError):
        packet.state = PacketState.SUPERSEDED
    with pytest.raises(FrozenInstanceError):
        packet.target_sha = "sha-new"

def test_evaluate_packet_retention_when_sha_and_host_safe():
    packet = WorkPacket(id="p-retain", owner_id="writer-alpha", target_sha="sha-good", state=PacketState.CURRENT)
    evaluated = evaluate_packet(packet, current_sha="sha-good", host_safe=True)
    assert evaluated == packet
    assert evaluated.state == PacketState.CURRENT

def test_evaluate_packet_superseded_takes_precedence_over_unsafe_host():
    # If both SHA diverges and host is unsafe, state must become SUPERSEDED (diverged SHA is stale)
    packet = WorkPacket(id="p-stale", owner_id="writer-alpha", target_sha="sha-old", state=PacketState.CURRENT)
    evaluated = evaluate_packet(packet, current_sha="sha-new", host_safe=False)
    assert evaluated.state == PacketState.SUPERSEDED

def test_evaluate_packet_superseded_is_terminal():
    packet = WorkPacket(id="p-term", owner_id="writer-alpha", target_sha="sha-dead", state=PacketState.SUPERSEDED)
    # Even if current_sha suddenly equals target_sha and host is safe, it cannot un-supersede
    evaluated = evaluate_packet(packet, current_sha="sha-dead", host_safe=True)
    assert evaluated.state == PacketState.SUPERSEDED

def test_evaluate_packet_parked_remains_parked_when_host_unsafe():
    packet = WorkPacket(id="p-park", owner_id="writer-alpha", target_sha="sha-1", state=PacketState.PARKED_BY_HOST)
    evaluated = evaluate_packet(packet, current_sha="sha-1", host_safe=False)
    assert evaluated.state == PacketState.PARKED_BY_HOST

def test_evaluate_packet_parked_becomes_superseded_if_sha_changes():
    packet = WorkPacket(id="p-park", owner_id="writer-alpha", target_sha="sha-1", state=PacketState.PARKED_BY_HOST)
    evaluated = evaluate_packet(packet, current_sha="sha-2", host_safe=True)
    assert evaluated.state == PacketState.SUPERSEDED

def test_packet_queue_empty():
    queue = PacketQueue()
    admissible = queue.get_admissible_packet(current_sha="sha-1", host_safe=True)
    assert admissible is None

def test_packet_queue_non_promotable_states():
    queue = PacketQueue()
    # States like WAITING_FOR_EVIDENCE or AFTER_NEXT should NOT be promoted to CURRENT
    queue.add_packet(WorkPacket("p-wait", "w1", "sha1", PacketState.WAITING_FOR_EVIDENCE))
    queue.add_packet(WorkPacket("p-after", "w2", "sha1", PacketState.AFTER_NEXT))
    
    admissible = queue.get_admissible_packet(current_sha="sha1", host_safe=True)
    assert admissible is None

def test_packet_queue_deterministic_fifo_promotion():
    queue = PacketQueue()
    queue.add_packet(WorkPacket("p-first", "w1", "sha1", PacketState.NEXT))
    queue.add_packet(WorkPacket("p-second", "w2", "sha1", PacketState.NEXT))
    queue.add_packet(WorkPacket("p-third", "w3", "sha1", PacketState.NEXT))
    
    # First NEXT gets promoted to CURRENT
    admissible1 = queue.get_admissible_packet(current_sha="sha1", host_safe=True)
    assert admissible1 is not None
    assert admissible1.id == "p-first"
    assert admissible1.state == PacketState.CURRENT
    
    # As long as p-first is CURRENT, subsequent calls retain p-first
    admissible2 = queue.get_admissible_packet(current_sha="sha1", host_safe=True)
    assert admissible2.id == "p-first"
    
    # If p-first is marked SUPERSEDED / evicted and SHA matches, p-second is promoted
    queue.packets["p-first"] = WorkPacket("p-first", "w1", "sha1", PacketState.SUPERSEDED)
    admissible3 = queue.get_admissible_packet(current_sha="sha1", host_safe=True)
    assert admissible3.id == "p-second"
    assert admissible3.state == PacketState.CURRENT

def test_packet_queue_sha_invalidation_cascades_to_all():
    queue = PacketQueue()
    queue.add_packet(WorkPacket("p1", "w1", "sha-old", PacketState.CURRENT))
    queue.add_packet(WorkPacket("p2", "w2", "sha-old", PacketState.NEXT))
    queue.add_packet(WorkPacket("p3", "w3", "sha-old", PacketState.WAITING_FOR_EVIDENCE))
    
    admissible = queue.get_admissible_packet(current_sha="sha-new", host_safe=True)
    assert admissible is None
    assert queue.packets["p1"].state == PacketState.SUPERSEDED
    assert queue.packets["p2"].state == PacketState.SUPERSEDED
    assert queue.packets["p3"].state == PacketState.SUPERSEDED
