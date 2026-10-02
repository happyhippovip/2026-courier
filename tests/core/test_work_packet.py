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
