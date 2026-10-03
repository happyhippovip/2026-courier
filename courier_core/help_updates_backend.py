from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional

class UpdateState(Enum):
    AVAILABLE = auto()
    DOWNLOADING = auto()
    READY_TO_INSTALL = auto()
    INSTALLED = auto()

@dataclass
class SupportTicket:
    ticket_id: str
    issue_type: str
    status: str

class HelpBackendContract:
    """MAC-25: Implement backend semantics for customer help/update state."""
    def __init__(self):
        self.update_state = UpdateState.INSTALLED
        self.pending_update_version: Optional[str] = None
        self.tickets: dict[str, SupportTicket] = {}

    def publish_update(self, version: str) -> None:
        self.update_state = UpdateState.AVAILABLE
        self.pending_update_version = version

    def acknowledge_update_ready(self) -> None:
        if self.update_state in (UpdateState.AVAILABLE, UpdateState.DOWNLOADING):
            self.update_state = UpdateState.READY_TO_INSTALL

    def create_support_ticket(self, ticket_id: str, issue_type: str) -> SupportTicket:
        ticket = SupportTicket(ticket_id, issue_type, "OPEN")
        self.tickets[ticket_id] = ticket
        return ticket
