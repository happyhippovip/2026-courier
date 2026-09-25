import re
with open("tests/test_server_integration_contract.py", "r") as f:
    text = f.read()

old_code = """
        failed = durable_result(task)
        failed["status"] = "FAILED"
        failed["artifacts"] = []
        failed["result_id"] = "result-" + _canonical_hash(failed)
"""
new_code = """
        failed = durable_result(task)
        failed["status"] = "FAILED"
        failed["artifacts"] = []
        ident = {k: v for k, v in failed.items() if k not in ("run_id", "result_id")}
        failed["result_id"] = "result-" + _canonical_hash(ident)
"""
text = text.replace(old_code.strip(), new_code.strip())
text = text.replace("r = http.post(\"/tasks/result\", headers=auth(), json=failed); print('BODY:', r.get_data(as_text=True)); assert r.status_code == 200", "assert http.post(\"/tasks/result\", headers=auth(), json=failed).status_code == 200")
with open("tests/test_server_integration_contract.py", "w") as f:
    f.write(text)
