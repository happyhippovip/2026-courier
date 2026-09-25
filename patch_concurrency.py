import re
with open("tests/test_turbo_queue_concurrency.py", "r") as f:
    c = f.read()

c = c.replace(
    '"worker_id": w_id, "run_id": f"run_{tid}", "result_id": f"res_{tid}",',
    '"worker_id": w_id, "run_id": f"run_{tid}", "result_id": f"res_{tid}", "runtime_identity": task.get("server_binding"),'
)
# And set canonical hash
c = c.replace(
    'requests.post(f"{test_server}/tasks/result", json=result, headers=auth_worker)',
    'result["result_id"] = f"result-{_canonical_hash(result)}"; r = requests.post(f"{test_server}/tasks/result", json=result, headers=auth_worker); assert r.status_code == 200, r.text'
)
with open("tests/test_turbo_queue_concurrency.py", "w") as f:
    f.write(c)

