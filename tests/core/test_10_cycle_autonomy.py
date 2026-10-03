from courier_core.ide_acceptance_gate import AcceptanceGate, IdeSurfaceState, PendingChange
from courier_core.recovery_state_machine import RecoveryState, RecoveryStateMachine, TransitionRequest

def test_10_cycle_autonomy():
    gate = AcceptanceGate(authorized_writer_id="MAC_WRITER", permitted_scopes=["courier_core/"])
    state_machine = RecoveryStateMachine()
    
    # We simulate 10 queued tasks
    queued_tasks = 10
    
    log = []
    
    for cycle in range(1, 11):
        # Agent edits
        change = [PendingChange(f"courier_core/file_{cycle}.py", "MAC_WRITER", False, False, False)]
        
        # IDE Review Gate occurs
        surface = IdeSurfaceState(
            is_review_changes_visible=True,
            is_accept_all_visible=True,
            queued_messages_count=queued_tasks - 1, # decrements as we process
            agent_actively_editing=False
        )
        
        # Courier recognizes and safely accepts
        new_state = gate.process_review_gate(surface, change, tests_pass=True, workspace_reconciled=True)
        
        # Apply transition
        state_machine.transition(TransitionRequest(f"CYCLE_{cycle}_COMPLETE", new_state, "safe auto accept"))
        
        log.append({
            "CYCLE": cycle,
            "REVIEW_GATE_SEEN": True,
            "AUTO_ACCEPTED": new_state in (RecoveryState.EXECUTING, RecoveryState.IDLE_READY),
            "WHY_SAFE": "Matching writer, in-scope, no user mixed edits",
            "TEST_RESULT": "PASS",
            "NEXT_WORK_STARTED": True if surface.queued_messages_count > 0 else False,
            "HUMAN_ACTION_REQUIRED": "NONE"
        })
        
        queued_tasks -= 1
        
        # If there's more work, it must be EXECUTING. If empty, IDLE_READY.
        if queued_tasks > 0:
            assert state_machine.state == RecoveryState.EXECUTING
        else:
            assert state_machine.state == RecoveryState.IDLE_READY
            
    assert len(log) == 10
    assert log[-1]["NEXT_WORK_STARTED"] == False
    assert state_machine.state == RecoveryState.IDLE_READY

if __name__ == "__main__":
    test_10_cycle_autonomy()
    print("10-Cycle Autonomy Test Passed.")

