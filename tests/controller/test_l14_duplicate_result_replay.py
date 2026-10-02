import pytest
from courier_core.controller import ApiError
from ctrl_helpers import make_controller, FakeClock

def test_l14_attack_duplicate_result_replay(tmp_path):
    clock = FakeClock()
    ctl = make_controller(tmp_path / "home", clock=clock)
    
    t = ctl.create_task({"adapter": "dummy", "params": {}, "effect_class": "idempotent", "max_attempts": 3, "lease_ttl_s": 60})
    task_id = t[1]["task_id"]
    
    lease = ctl.claim({"worker_id": "w1"})
    dispatch_id = lease["dispatch_id"]
    ctl.start({"dispatch_id": dispatch_id, "worker_id": "w1"})
    
    # 1. Send result A
    ctl.result({"dispatch_id": dispatch_id, "result_id": "res_A", "outcome": "success", "artifacts": []})
    
    # 2. Worker crashes. Re-claims the same task.
    # But wait, task is VERIFYING, worker cannot claim it.
    
    # 3. Attacker replays exact duplicate
    status, body = ctl.result({"dispatch_id": dispatch_id, "result_id": "res_A", "outcome": "success", "artifacts": []})
    
    # 4. Attacker sends a DIFFERENT result_id
    try:
        ctl.result({"dispatch_id": dispatch_id, "result_id": "res_B", "outcome": "failure", "reason": "different", "retryable": True, "artifacts": []})
    except ApiError as e:
        print("\nDifferent result_id:", e.status, e.body())
        
    ctl.stop()

