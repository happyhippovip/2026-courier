import pytest
from courier_core.controller import ApiError
from courier_core.state_machine import TaskStatus
from courier_core.verification import Verdict
from ctrl_helpers import make_controller, FakeClock, Verifiers

def test_l16_trace_result_ready_to_accepted(tmp_path):
    clock = FakeClock()
    
    # We create a mock verifier that explicitly accepts
    def dummy_verifier(task, result, home):
        return Verdict(True, "looks good", False, None)
        
    ctl = make_controller(tmp_path / "home", clock=clock, verifier=Verifiers(dummy=dummy_verifier))
    
    # Create and start task
    t = ctl.create_task({"adapter": "dummy", "params": {}, "effect_class": "idempotent", "max_attempts": 3, "lease_ttl_s": 60})
    task_id = t[1]["task_id"]
    lease = ctl.claim({"worker_id": "w1"})
    dispatch_id = lease["dispatch_id"]
    ctl.start({"dispatch_id": dispatch_id, "worker_id": "w1"})
    
    # 1. Post RESULT_READY
    status, body = ctl.result({"dispatch_id": dispatch_id, "result_id": "res1", "status": "SUCCESS", "artifacts": []})
    assert status == 200
    assert body["status"] == "ACCEPTED_FOR_VERIFY"
    
    # 2. State is VERIFYING
    task_verifying = ctl.task_view(task_id)
    assert task_verifying["status"] == TaskStatus.VERIFYING.value
    assert task_verifying["pending_result_id"] == "res1"
    
    # 3. Run verifier
    ctl.verify_next()
    
    # 4. State is COMPLETE (it passed through ACCEPTED)
    task_final = ctl.task_view(task_id)
    assert task_final["status"] == TaskStatus.COMPLETE.value
    assert task_final["accepted_result_id"] == "res1"
    assert task_final["resolution"] == "verified"
    
    # Check the exact event chain
    events = [e.type.value for e in ctl.events_after(0)]
    assert "RESULT_READY" in events
    assert "RESULT_ACCEPTED" in events
    assert "TASK_COMPLETE" in events
    
    ctl.stop()
