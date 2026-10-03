from courier_core.recovery_state_machine import RecoveryState
from courier_core.customer_status import translate_status, CustomerStatus

def test_working_translations():
    assert translate_status(RecoveryState.EXECUTING) == CustomerStatus.WORKING
    assert translate_status(RecoveryState.IDLE_READY) == CustomerStatus.WORKING

def test_needs_you_translations():
    assert translate_status(RecoveryState.WAITING_FOR_USER_PERMISSION) == CustomerStatus.NEEDS_YOU
    assert translate_status(RecoveryState.WAITING_FOR_OS_PERMISSION) == CustomerStatus.NEEDS_YOU

def test_recovering_translations():
    assert translate_status(RecoveryState.TERMINAL_HOST_FAILED) == CustomerStatus.RECOVERING
    assert translate_status(RecoveryState.SURFACE_CORRUPTED) == CustomerStatus.RECOVERING
