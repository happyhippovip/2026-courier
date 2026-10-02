from tests.controller.ctrl_helpers import make_controller, task_body, api_error, run_attempt

def test_start_requires_matching_worker_id_or_returns_409(tmp_path):
    ctl = make_controller(tmp_path / "home")
    try:
        _, body = ctl.create_task(task_body())
        lease = ctl.claim({"worker_id": "w1"})
        
        # Test missing worker_id (if API allows it)
        # We might not be able to enforce this if it's considered valid by dispatch_id secrecy, but let's test the mismatch
        err = api_error(ctl.start, {"dispatch_id": lease["dispatch_id"], "worker_id": "w2"})
        assert err.status == 409
        assert err.code == "wrong_worker"
        
        # Proper worker_id succeeds
        res = ctl.start({"dispatch_id": lease["dispatch_id"], "worker_id": "w1"})
        assert res["status"] == "RUNNING"
    finally:
        ctl.stop()

def test_result_requires_matching_worker_id(tmp_path):
    ctl = make_controller(tmp_path / "home")
    try:
        _, body = ctl.create_task(task_body())
        lease = ctl.claim({"worker_id": "w1"})
        ctl.start({"dispatch_id": lease["dispatch_id"], "worker_id": "w1"})
        
        err = api_error(ctl.result, {"dispatch_id": lease["dispatch_id"], "worker_id": "w2", "outcome": "success"})
        assert err.status == 409
        assert err.code == "wrong_worker"
    finally:
        ctl.stop()
