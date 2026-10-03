from enum import Enum
from courier_core.recovery_state_machine import RecoveryState

class CustomerStatus(Enum):
    WORKING = "WORKING"
    NEEDS_YOU = "NEEDS_YOU"
    RECOVERING = "RECOVERING"
    DONE = "DONE"

def translate_status(internal_state: RecoveryState) -> CustomerStatus:
    if internal_state in (RecoveryState.IDLE_READY, RecoveryState.EXECUTING):
        return CustomerStatus.WORKING
    elif internal_state in (RecoveryState.WAITING_FOR_USER_PERMISSION, RecoveryState.WAITING_FOR_OS_PERMISSION, RecoveryState.NEEDS_YOU):
        return CustomerStatus.NEEDS_YOU
    elif internal_state in (RecoveryState.TERMINAL_HOST_FAILED, RecoveryState.SURFACE_CORRUPTED, RecoveryState.RECOVERING):
        return CustomerStatus.RECOVERING
    else:
        return CustomerStatus.WORKING # Safe fallback
