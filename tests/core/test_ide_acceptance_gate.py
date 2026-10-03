from courier_core.ide_acceptance_gate import AcceptanceGate, IdeSurfaceState, PendingChange
from courier_core.recovery_state_machine import RecoveryState

def test_acceptance_gate_scenarios():
    gate = AcceptanceGate(authorized_writer_id="MAC_WRITER", permitted_scopes=["tests/", "courier_core/"])
    
    # Base surface showing the review gate pattern
    blocked_surface = IdeSurfaceState(
        is_review_changes_visible=True,
        is_accept_all_visible=True,
        queued_messages_count=1,
        agent_actively_editing=False
    )
    
    # 1. Agent changes one owned file; safe auto-accept; next queue item starts.
    safe_change = [PendingChange("courier_core/new.py", "MAC_WRITER", False, False, False)]
    res = gate.process_review_gate(blocked_surface, safe_change, tests_pass=True)
    assert res == RecoveryState.EXECUTING
    
    # 2. Agent changes many owned files; safe auto-accept.
    many_safe_changes = [
        PendingChange("courier_core/new1.py", "MAC_WRITER", False, False, False),
        PendingChange("tests/core/test_new1.py", "MAC_WRITER", False, False, False)
    ]
    res = gate.process_review_gate(blocked_surface, many_safe_changes, tests_pass=True)
    assert res == RecoveryState.EXECUTING

    # 3. User-edited file mixed into review; DO NOT auto-accept.
    user_mixed_changes = [
        PendingChange("courier_core/new.py", "MAC_WRITER", False, False, False),
        PendingChange("tests/user_test.py", "MAC_WRITER", True, False, False)
    ]
    res = gate.process_review_gate(blocked_surface, user_mixed_changes, tests_pass=True)
    assert res == RecoveryState.WAITING_FOR_USER_ACCEPTANCE

    # 4. Another writer owns one changed file; DO NOT auto-accept.
    wrong_writer_changes = [PendingChange("courier_core/new.py", "WINDOWS_WRITER", False, False, False)]
    res = gate.process_review_gate(blocked_surface, wrong_writer_changes, tests_pass=True)
    assert res == RecoveryState.WAITING_FOR_USER_ACCEPTANCE
    
    # 5. Merge conflict; DO NOT auto-accept.
    conflict_changes = [PendingChange("courier_core/new.py", "MAC_WRITER", False, True, False)]
    res = gate.process_review_gate(blocked_surface, conflict_changes, tests_pass=True)
    assert res == RecoveryState.WAITING_FOR_USER_ACCEPTANCE

    # 6. Permission-sensitive action included; require user.
    sensitive_changes = [PendingChange("courier_core/new.py", "MAC_WRITER", False, False, True)]
    res = gate.process_review_gate(blocked_surface, sensitive_changes, tests_pass=True)
    assert res == RecoveryState.WAITING_FOR_USER_ACCEPTANCE

    # 7. Review accepted but tests fail; do not mark DONE.
    res = gate.process_review_gate(blocked_surface, safe_change, tests_pass=False)
    assert res == RecoveryState.FAILED

    # 8. Review accepted and queue empty; IDLE_READY.
    empty_queue_surface = IdeSurfaceState(True, True, 0, False)
    res = gate.process_review_gate(empty_queue_surface, safe_change, tests_pass=True)
    assert res == RecoveryState.IDLE_READY

    # 9. Review accepted and queue non-empty; auto-continue.
    # Handled in #1 (returns EXECUTING)

    # 10. IDE/review surface disappears unexpectedly; reconcile actual filesystem state before deciding
    disappeared_surface = IdeSurfaceState(False, False, 1, False)
    res = gate.process_review_gate(disappeared_surface, safe_change, tests_pass=True, workspace_reconciled=False)
    assert res == RecoveryState.RECOVERING

