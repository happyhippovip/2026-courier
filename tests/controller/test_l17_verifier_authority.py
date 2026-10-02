import pytest
from pathlib import Path
from courier_core.controller import ApiError
from courier_core.state_machine import TaskStatus
from courier_core.verification import Verdict
from ctrl_helpers import make_controller, FakeClock, Verifiers

def malicious_verifier(task, result, home):
    # The verifier attempts to create authority by spoofing its identity
    return Verdict(accepted=True, reason="Spoofed", retryable=False, verifier={"kind": "admin", "name": "root_overlord"})

def test_l17_verifier_cannot_create_authority(tmp_path):
    clock = FakeClock()
    ctl = make_controller(tmp_path / "home", clock=clock, verifier=Verifiers(dummy=malicious_verifier))
    
    t = ctl.create_task({"adapter": "dummy", "params": {}, "effect_class": "idempotent", "max_attempts": 3, "lease_ttl_s": 60})
    task_id = t[1]["task_id"]
    lease = ctl.claim({"worker_id": "w1"})
    dispatch_id = lease["dispatch_id"]
    ctl.start({"dispatch_id": dispatch_id, "worker_id": "w1"})
    
    ctl.result({"dispatch_id": dispatch_id, "result_id": "res1", "outcome": "success", "artifacts": []})
    
    # Run verifier
    ctl.verify_next()
    
    events_accepted = [e for e in ctl.events_after(0) if e.type.value == "RESULT_ACCEPTED"]
    assert len(events_accepted) == 1
    
    recorded_verifier = events_accepted[0].payload["verifier"]
    
    # The verifier explicitly attempted to set kind="admin" and name="root_overlord"
    # Prove that this authority was overwritten by the controller's structural boundary
    assert recorded_verifier.get("kind") != "admin"
    assert recorded_verifier.get("name") != "root_overlord"
    assert recorded_verifier.get("kind") == "adapter"
    assert "wrapped" in recorded_verifier.get("name")
    
    ctl.stop()
