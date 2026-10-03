from enum import Enum, auto

class DeliveryState(Enum):
    APPROVED = auto()
    PLANNED = auto()
    AUTHORIZED = auto()
    EXECUTING = auto()
    VERIFYING = auto()
    DELIVERED = auto()
    FAILED = auto()

class DeliveryStateMachine:
    """MAC-17: Delivery Agent State Machine."""
    def __init__(self):
        self.state = DeliveryState.APPROVED

    def transition(self, next_state: DeliveryState) -> bool:
        valid_transitions = {
            DeliveryState.APPROVED: [DeliveryState.PLANNED, DeliveryState.FAILED],
            DeliveryState.PLANNED: [DeliveryState.AUTHORIZED, DeliveryState.FAILED],
            DeliveryState.AUTHORIZED: [DeliveryState.EXECUTING, DeliveryState.FAILED],
            DeliveryState.EXECUTING: [DeliveryState.VERIFYING, DeliveryState.FAILED],
            DeliveryState.VERIFYING: [DeliveryState.DELIVERED, DeliveryState.FAILED],
            DeliveryState.DELIVERED: [],
            DeliveryState.FAILED: []
        }
        
        if next_state in valid_transitions.get(self.state, []):
            self.state = next_state
            return True
        return False
