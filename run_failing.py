import os, sys, traceback, tempfile
os.environ["COURIER_API_KEY"] = "test-api-key"
os.environ["COURIER_VERIFIER_API_KEY"] = "test-verifier-key"

import server.app as sapp
from tests.test_server_app_uncovered import (
    test_pending_verification,
    test_verify_task_result_unknown,
    test_verify_task_result_duplicate,
    test_verify_task_result_not_ready,
    test_verify_task_result_invalid_verdict,
    test_resume_task_success
)

with tempfile.TemporaryDirectory() as td:
    sapp.STATE_FILE = os.path.join(td, "state.json")
    app = sapp.app.test_client()

    for func in [test_pending_verification, test_verify_task_result_unknown, test_verify_task_result_duplicate, test_verify_task_result_not_ready, test_verify_task_result_invalid_verdict, test_resume_task_success]:
        try:
            func(app)
            print(f"{func.__name__} passed")
        except Exception as e:
            print(f"{func.__name__} failed:")
            traceback.print_exc()
