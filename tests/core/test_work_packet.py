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


def test_evaluate_leaves_current_unchanged_when_sha_matches_and_host_safe():
    packet = WorkPacket(id="p5", owner_id="writer1", target_sha="sha1", state=PacketState.CURRENT)
    new_packet = evaluate_packet(packet, current_sha="sha1", host_safe=True)
    assert new_packet is packet
    assert new_packet.state == PacketState.CURRENT


def test_evaluate_passes_through_waiting_and_after_next_when_admissible():
    for state in (PacketState.WAITING_FOR_EVIDENCE, PacketState.AFTER_NEXT):
        packet = WorkPacket(id="p6", owner_id="writer1", target_sha="sha1", state=state)
        new_packet = evaluate_packet(packet, current_sha="sha1", host_safe=True)
        assert new_packet is packet
        assert new_packet.state is state


def test_packet_queue_empty_returns_none():
    queue = PacketQueue()
    assert queue.get_admissible_packet("sha1", host_safe=True) is None


def test_packet_queue_supersedes_stale_current_then_promotes_next():
    queue = PacketQueue()
    queue.add_packet(WorkPacket("p1", "w1", "sha-old", PacketState.CURRENT))
    queue.add_packet(WorkPacket("p2", "w2", "sha-new", PacketState.NEXT))
    admissible = queue.get_admissible_packet("sha-new", host_safe=True)
    assert queue.packets["p1"].state == PacketState.SUPERSEDED
    assert admissible is not None
    assert admissible.id == "p2"
    assert admissible.state == PacketState.CURRENT
