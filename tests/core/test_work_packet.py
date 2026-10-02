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
