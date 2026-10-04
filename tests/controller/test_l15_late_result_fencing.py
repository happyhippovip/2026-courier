import pytest
from courier_core.controller import ApiError
from courier_core.state_machine import TaskStatus
from ctrl_helpers import make_controller, FakeClock

def test_l15_attack_stale_worker_write_after_transfer(tmp_path):
    clock = FakeClock()
    ctl = make_controller(tmp_path / "home", clock=clock)
    
    # 1. Create a task
    t = ctl.create_task({"adapter": "dummy", "params": {}, "effect_class": "idempotent", "max_attempts": 3, "lease_ttl_s": 60})
    task_id = t[1]["task_id"]
    
    # 2. Worker 1 claims and starts the task
    lease1 = ctl.claim({"worker_id": "w1"})
    dispatch1 = lease1["dispatch_id"]
    ctl.start({"dispatch_id": dispatch1, "worker_id": "w1"})
    
    # 3. Worker 1 is slow, lease expires. Controller ticks.
    clock.advance(65)
    ctl.tick()
    
    task_after_expire = ctl.task_view(task_id)
    assert task_after_expire["status"] == TaskStatus.QUEUED.value
    
    # 4. Worker 2 claims and starts the task (transfer)
    lease2 = ctl.claim({"worker_id": "w2"})
    dispatch2 = lease2["dispatch_id"]
    ctl.start({"dispatch_id": dispatch2, "worker_id": "w2"})
    
    assert dispatch1 != dispatch2
    
    # 5. Attack: Worker 1 (stale) finally finishes and tries to write result (write-after-transfer)
    try:
        ctl.result({"dispatch_id": dispatch1, "result_id": "res_w1", "status": "SUCCESS", "artifacts": []})
        pytest.fail("Stale worker was allowed to post a result after transfer")
    except ApiError as e:
        assert e.status == 409
        assert e.code == "stale_dispatch"
    
    # 6. Verify that Worker 1's result was recorded as LATE_RESULT_DISCARDED and task is still RUNNING for w2
    task_after_stale_write = ctl.task_view(task_id)
    assert task_after_stale_write["status"] == TaskStatus.RUNNING.value
    assert task_after_stale_write["dispatch_id"] == dispatch2
    assert task_after_stale_write["late_results"] == 1
    
    # 7. Worker 2 writes result successfully
    status, body = ctl.result({"dispatch_id": dispatch2, "result_id": "res_w2", "status": "SUCCESS", "artifacts": []})
    assert status == 200
    assert body["status"] == "ACCEPTED_FOR_VERIFY"
    
    task_final = ctl.task_view(task_id)
    assert task_final["status"] == TaskStatus.VERIFYING.value
    assert task_final["dispatch_id"] == dispatch2
    
    ctl.stop()
