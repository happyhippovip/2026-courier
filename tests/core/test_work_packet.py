from courier_core.work_packet import PacketState, WorkPacket, evaluate_packet

def test_packet_superseded_when_sha_changes():
    packet = WorkPacket(id="p1", owner_id="writer1", target_sha="sha1", state=PacketState.CURRENT)
    new_packet = evaluate_packet(packet, current_sha="sha2", host_safe=True)
    assert new_packet.state == PacketState.SUPERSEDED

def test_packet_parked_when_host_unsafe():
    packet = WorkPacket(id="p2", owner_id="writer1", target_sha="sha1", state=PacketState.CURRENT)
    new_packet = evaluate_packet(packet, current_sha="sha1", host_safe=False)
    assert new_packet.state == PacketState.PARKED_BY_HOST

def test_packet_wakes_up_when_host_recovers():
    packet = WorkPacket(id="p3", owner_id="writer1", target_sha="sha1", state=PacketState.PARKED_BY_HOST)
    new_packet = evaluate_packet(packet, current_sha="sha1", host_safe=True)
    assert new_packet.state == PacketState.CURRENT

def test_superseded_stays_superseded():
    packet = WorkPacket(id="p4", owner_id="writer1", target_sha="sha1", state=PacketState.SUPERSEDED)
    new_packet = evaluate_packet(packet, current_sha="sha1", host_safe=True)
    assert new_packet.state == PacketState.SUPERSEDED

from courier_core.work_packet import PacketQueue

def test_packet_queue_enforces_one_writer():
    queue = PacketQueue()
    queue.add_packet(WorkPacket("p1", "w1", "sha1", PacketState.CURRENT))
    queue.add_packet(WorkPacket("p2", "w2", "sha1", PacketState.NEXT))
    
    admissible = queue.get_admissible_packet("sha1", host_safe=True)
    assert admissible.id == "p1"
    assert admissible.state == PacketState.CURRENT

def test_packet_queue_promotes_next_when_idle():
    queue = PacketQueue()
    queue.add_packet(WorkPacket("p2", "w2", "sha1", PacketState.NEXT))
    
    admissible = queue.get_admissible_packet("sha1", host_safe=True)
    assert admissible.id == "p2"
    assert admissible.state == PacketState.CURRENT

def test_packet_queue_blocks_promotion_when_host_unsafe():
    queue = PacketQueue()
    queue.add_packet(WorkPacket("p2", "w2", "sha1", PacketState.NEXT))
    
    admissible = queue.get_admissible_packet("sha1", host_safe=False)
    assert admissible is None
    assert queue.packets["p2"].state == PacketState.PARKED_BY_HOST

def test_supersede_takes_precedence_over_park():
    packet = WorkPacket(id="p1", owner_id="w1", target_sha="sha1", state=PacketState.PARKED_BY_HOST)
    new_packet = evaluate_packet(packet, current_sha="sha2", host_safe=False)
    assert new_packet.state == PacketState.SUPERSEDED

def test_stale_sha_with_unsafe_host_supersedes():
    packet = WorkPacket(id="p1", owner_id="w1", target_sha="sha1", state=PacketState.CURRENT)
    new_packet = evaluate_packet(packet, current_sha="sha2", host_safe=False)
    assert new_packet.state == PacketState.SUPERSEDED

def test_matching_sha_safe_returns_packet_unchanged():
    packet = WorkPacket(id="p1", owner_id="w1", target_sha="sha1", state=PacketState.CURRENT)
    new_packet = evaluate_packet(packet, current_sha="sha1", host_safe=True)
    assert new_packet is packet
    assert new_packet.state == PacketState.CURRENT

def test_next_packet_not_auto_promoted_by_evaluate():
    packet = WorkPacket(id="p1", owner_id="w1", target_sha="sha1", state=PacketState.NEXT)
    new_packet = evaluate_packet(packet, current_sha="sha1", host_safe=True)
    assert new_packet.state == PacketState.NEXT

def test_waiting_for_evidence_preserved_when_safe():
    packet = WorkPacket(id="p1", owner_id="w1", target_sha="sha1", state=PacketState.WAITING_FOR_EVIDENCE)
    new_packet = evaluate_packet(packet, current_sha="sha1", host_safe=True)
    assert new_packet is packet
    assert new_packet.state == PacketState.WAITING_FOR_EVIDENCE

def test_after_next_parked_when_host_unsafe():
    packet = WorkPacket(id="p1", owner_id="w1", target_sha="sha1", state=PacketState.AFTER_NEXT)
    new_packet = evaluate_packet(packet, current_sha="sha1", host_safe=False)
    assert new_packet.state == PacketState.PARKED_BY_HOST

def test_evaluate_preserves_identity_fields():
    packet = WorkPacket(id="p1", owner_id="w1", target_sha="sha1", state=PacketState.CURRENT)
    superseded = evaluate_packet(packet, current_sha="sha2", host_safe=True)
    assert (superseded.id, superseded.owner_id, superseded.target_sha) == ("p1", "w1", "sha1")
    parked = evaluate_packet(packet, current_sha="sha1", host_safe=False)
    assert (parked.id, parked.owner_id, parked.target_sha) == ("p1", "w1", "sha1")

def test_evaluate_does_not_mutate_input():
    packet = WorkPacket(id="p1", owner_id="w1", target_sha="sha1", state=PacketState.CURRENT)
    evaluate_packet(packet, current_sha="sha1", host_safe=False)
    assert packet.state == PacketState.CURRENT

def test_empty_queue_returns_none():
    queue = PacketQueue()
    assert queue.get_admissible_packet("sha1", host_safe=True) is None

def test_multiple_currents_first_wins():
    queue = PacketQueue()
    queue.add_packet(WorkPacket("p1", "w1", "sha1", PacketState.CURRENT))
    queue.add_packet(WorkPacket("p2", "w2", "sha1", PacketState.CURRENT))
    admissible = queue.get_admissible_packet("sha1", host_safe=True)
    assert admissible.id == "p1"
    assert admissible.state == PacketState.CURRENT

def test_stale_current_superseded_and_next_promoted():
    queue = PacketQueue()
    queue.add_packet(WorkPacket("p1", "w1", "sha-old", PacketState.CURRENT))
    queue.add_packet(WorkPacket("p2", "w2", "sha1", PacketState.NEXT))
    admissible = queue.get_admissible_packet("sha1", host_safe=True)
    assert admissible.id == "p2"
    assert admissible.state == PacketState.CURRENT
    assert queue.packets["p1"].state == PacketState.SUPERSEDED

def test_stale_next_never_promoted():
    queue = PacketQueue()
    queue.add_packet(WorkPacket("p2", "w2", "sha-old", PacketState.NEXT))
    admissible = queue.get_admissible_packet("sha1", host_safe=True)
    assert admissible is None
    assert queue.packets["p2"].state == PacketState.SUPERSEDED

def test_waiting_for_evidence_never_promoted():
    queue = PacketQueue()
    queue.add_packet(WorkPacket("p1", "w1", "sha1", PacketState.WAITING_FOR_EVIDENCE))
    admissible = queue.get_admissible_packet("sha1", host_safe=True)
    assert admissible is None
    assert queue.packets["p1"].state == PacketState.WAITING_FOR_EVIDENCE

def test_current_parked_when_host_unsafe():
    queue = PacketQueue()
    queue.add_packet(WorkPacket("p1", "w1", "sha1", PacketState.CURRENT))
    admissible = queue.get_admissible_packet("sha1", host_safe=False)
    assert admissible is None
    assert queue.packets["p1"].state == PacketState.PARKED_BY_HOST

def test_add_packet_overwrites_same_id():
    queue = PacketQueue()
    queue.add_packet(WorkPacket("p1", "w1", "sha1", PacketState.NEXT))
    queue.add_packet(WorkPacket("p1", "w2", "sha1", PacketState.CURRENT))
    admissible = queue.get_admissible_packet("sha1", host_safe=True)
    assert admissible.owner_id == "w2"
    assert admissible.state == PacketState.CURRENT
