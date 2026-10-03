from enum import Enum, auto
from typing import List

class RevenueState(Enum):
    PROSPECT = auto()
    QUALIFIED = auto()
    DRAFT_READY = auto()
    WAITING_FOR_HUMAN = auto()
    CONTACTED = auto()
    REPLIED = auto()
    PROPOSAL = auto()
    WON = auto()
    LOST = auto()

class RevenueStateMachine:
    """MAC-16: Revenue Agent State Machine (No real outreach)."""
    def __init__(self):
        self.state = RevenueState.PROSPECT

    def transition(self, next_state: RevenueState) -> bool:
        # Enforce linear pipeline safety
        valid_transitions = {
            RevenueState.PROSPECT: [RevenueState.QUALIFIED, RevenueState.LOST],
            RevenueState.QUALIFIED: [RevenueState.DRAFT_READY, RevenueState.LOST],
            RevenueState.DRAFT_READY: [RevenueState.WAITING_FOR_HUMAN, RevenueState.LOST],
            RevenueState.WAITING_FOR_HUMAN: [RevenueState.CONTACTED, RevenueState.LOST],
            RevenueState.CONTACTED: [RevenueState.REPLIED, RevenueState.LOST],
            RevenueState.REPLIED: [RevenueState.PROPOSAL, RevenueState.LOST],
            RevenueState.PROPOSAL: [RevenueState.WON, RevenueState.LOST],
            RevenueState.WON: [],
            RevenueState.LOST: []
        }
        
        if next_state in valid_transitions.get(self.state, []):
            self.state = next_state
            return True
        return False
