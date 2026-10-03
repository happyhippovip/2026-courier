from tests.controller.ctrl_helpers import make_controller, task_body, run_attempt
from courier_core.controller import ApiError
import pytest

def api_error(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        raise Exception("Expected ApiError")
    except ApiError as e:
        return e

def test_start_requires_matching_worker_id_or_returns_409(tmp_path):
    ctl = make_controller(tmp_path / "home")
    try:
        _, body = ctl.create_task(task_body())
        lease = ctl.claim({"worker_id": "w1"})
        
        err = api_error(ctl.start, {"dispatch_id": lease["dispatch_id"], "worker_id": "w2"})
        assert err.status == 409
        assert err.code == "wrong_worker"
        
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
