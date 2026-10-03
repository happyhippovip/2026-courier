from enum import Enum
from dataclasses import dataclass
from typing import Optional, List

class RecoveryState(Enum):
    IDLE_READY = "IDLE_READY"
    TERMINAL_HOST_FAILED = "TERMINAL_HOST_FAILED"
    WAITING_FOR_USER_PERMISSION = "WAITING_FOR_USER_PERMISSION"
    WAITING_FOR_OS_PERMISSION = "WAITING_FOR_OS_PERMISSION"
    SURFACE_CORRUPTED = "SURFACE_CORRUPTED"
    EXECUTING = "EXECUTING"
    RECOVERING = "RECOVERING"
    NEEDS_YOU = "NEEDS_YOU"
    WAITING_FOR_CHANGE_ACCEPTANCE = "WAITING_FOR_CHANGE_ACCEPTANCE"
    WAITING_FOR_USER_ACCEPTANCE = "WAITING_FOR_USER_ACCEPTANCE"
    FAILED = "FAILED"

@dataclass
class TransitionRequest:
    event: str
    target_state: RecoveryState
    reason: str
    evidence_id: Optional[str] = None

class RecoveryStateMachine:
    def __init__(self):
        self.state = RecoveryState.IDLE_READY
        self.history: List[TransitionRequest] = []

    def transition(self, request: TransitionRequest) -> bool:
        # Prevent silent inflation or invalid moves
        if self.state == RecoveryState.TERMINAL_HOST_FAILED:
            # Requires full-system recovery, not just soft reset
            if request.target_state != RecoveryState.IDLE_READY or request.event != "HARD_RESET":
                return False

        if self.state == RecoveryState.SURFACE_CORRUPTED:
            # Must run repair
            if request.target_state not in (RecoveryState.RECOVERING, RecoveryState.NEEDS_YOU):
                return False

        # Apply transition
        self.state = request.target_state
        self.history.append(request)
        return True
