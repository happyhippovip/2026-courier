import enum
from dataclasses import dataclass, replace
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
    parked_from: Optional[PacketState] = None

def evaluate_packet(packet: WorkPacket, current_sha: str, host_safe: bool) -> WorkPacket:
    """
    Evaluates a packet's state based on the current host admission and authoritative project truth (SHA).
    If the SHA has moved, the packet is stale and becomes SUPERSEDED.
    If the host is unsafe, the packet is PARKED_BY_HOST (unless already SUPERSEDED)
    and the prior state is remembered in parked_from. A repeated unsafe tick
    does not overwrite that memory.
    A safe host restores parked_from. A parked packet with no memory becomes
    CURRENT, matching packets constructed directly as PARKED_BY_HOST.
    """
    if packet.state == PacketState.SUPERSEDED:
        return packet

    if packet.target_sha != current_sha:
        return replace(packet, state=PacketState.SUPERSEDED, parked_from=None)

    if not host_safe:
        if packet.state == PacketState.PARKED_BY_HOST:
            return packet
        return replace(
            packet,
            state=PacketState.PARKED_BY_HOST,
            parked_from=packet.state,
        )

    if packet.state == PacketState.PARKED_BY_HOST and host_safe:
        restored = packet.parked_from if packet.parked_from is not None else PacketState.CURRENT
        return replace(packet, state=restored, parked_from=None)

    return packet

class PacketQueue:
    def __init__(self):
        self.packets: dict[str, WorkPacket] = {}

    def add_packet(self, packet: WorkPacket):
        self.packets[packet.id] = packet

    def get_admissible_packet(self, current_sha: str, host_safe: bool) -> Optional[WorkPacket]:
        """
        Enforces one-writer ownership and host admission limits.
        If a CURRENT packet exists, it retains the lock.
        Otherwise, if the host is safe, a NEXT packet is promoted to CURRENT.
        After evaluation, at most one CURRENT remains: the first in insertion
        order. Any other CURRENT is returned to NEXT, and a NEXT is never
        promoted while a CURRENT exists.
        """
        self.packets = {
            pid: evaluate_packet(packet, current_sha, host_safe)
            for pid, packet in self.packets.items()
        }

        kept_current = False
        normalized: dict[str, WorkPacket] = {}
        for pid, packet in self.packets.items():
            if packet.state == PacketState.CURRENT and kept_current:
                packet = replace(packet, state=PacketState.NEXT)
            elif packet.state == PacketState.CURRENT:
                kept_current = True
            normalized[pid] = packet
        self.packets = normalized

        for packet in self.packets.values():
            if packet.state == PacketState.CURRENT:
                return packet

        if host_safe:
            for packet in self.packets.values():
                if packet.state == PacketState.NEXT:
                    promoted = replace(packet, state=PacketState.CURRENT, parked_from=None)
                    self.packets[promoted.id] = promoted
                    return promoted

        return None
