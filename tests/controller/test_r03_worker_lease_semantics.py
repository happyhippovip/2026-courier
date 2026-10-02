from tests.controller.ctrl_helpers import make_controller, task_body, run_attempt

def test_r03_omitted_lease_in_heartbeat_expires_immediately(tmp_path):
    ctl = make_controller(tmp_path / "home")
    try:
        _, body = ctl.create_task(task_body(lease_ttl_s=3600))
        lease = ctl.claim({"worker_id": "w1"})
        
        # worker omits the dispatch_id in heartbeat
        ctl.heartbeat({"worker_id": "w1", "dispatch_ids": []})
        
        # In current flawed implementation, it just waits for TTL. 
        # A correct implementation would immediately expire the lease and queue it.
        task = ctl.journal.task(body["task_id"])
        
        # This will fail under the flawed implementation
        assert task.status.value == "QUEUED"
    finally:
        ctl.stop()
