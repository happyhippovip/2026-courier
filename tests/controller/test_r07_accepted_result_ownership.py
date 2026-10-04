from tests.controller.ctrl_helpers import make_controller, task_body

def test_r07_result_api_lacks_worker_identity_check(tmp_path):
    ctl = make_controller(tmp_path / "home")
    try:
        _, task = ctl.create_task(task_body())
        lease = ctl.claim({"worker_id": "worker_A"})
        dispatch_id = lease["dispatch_id"]

        ctl.start({"worker_id": "worker_A", "dispatch_id": dispatch_id})

        # worker_B calls result!
        # The result endpoint currently does not require or check worker_id
        res_status, res_body = ctl.result({
            "dispatch_id": dispatch_id,
            "result_id": "res_fake",
            "status": "SUCCESS",
            "artifacts": []
        })
        assert res_status == 200
        assert res_body["status"] == "ACCEPTED_FOR_VERIFY"
        
        # Now we verify it
        ctl.verify_next()
        t = ctl.journal.task(task["task_id"])
        
        # We can see that the result is complete. The result was submitted 
        # completely lacking any worker_id authentication in the API endpoint.
        assert t.status.name == "COMPLETE"
        assert t.accepted_result_id == "res_fake"
        # The worker_id on the task is worker_A, but a malicious worker_B submitted it.
        assert t.worker_id == "worker_A"

    finally:
        ctl.stop()
