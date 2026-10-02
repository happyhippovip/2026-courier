import enum
from dataclasses import dataclass
from typing import Optional

class PacketState(enum.Enum):
    CURRENT = "CURRENT"
    NEXT = "NEXT"
    AFTER_NEXT = "AFTER_NEXT"
    WAITING_FOR_EVIDENCE = "WAITING_FOR_EVIDENCE"
    SUPERSEDED = "SUPERSEDED"
    PARKED_BY_HOST = "PARKED_BY_HOST"

@dataclass(frozen=True)
class WorkPacket:
    id: str
    owner_id: str
    target_sha: str
    state: PacketState

def evaluate_packet(packet: WorkPacket, current_sha: str, host_safe: bool) -> WorkPacket:
    """
    Evaluates a packet's state based on the current host admission and authoritative project truth (SHA).
    If the SHA has moved, the packet is stale and becomes SUPERSEDED.
    If the host is unsafe, the packet is PARKED_BY_HOST (unless already SUPERSEDED).
    """
    if packet.state == PacketState.SUPERSEDED:
        return packet
        
    if packet.target_sha != current_sha:
        return WorkPacket(
            id=packet.id,
            owner_id=packet.owner_id,
            target_sha=packet.target_sha,
            state=PacketState.SUPERSEDED
        )
        
    if not host_safe:
        return WorkPacket(
            id=packet.id,
            owner_id=packet.owner_id,
            target_sha=packet.target_sha,
            state=PacketState.PARKED_BY_HOST
        )
        
    # Wake up from park
    if packet.state == PacketState.PARKED_BY_HOST and host_safe:
        return WorkPacket(
            id=packet.id,
            owner_id=packet.owner_id,
            target_sha=packet.target_sha,
            state=PacketState.CURRENT
        )
        
    return packet
