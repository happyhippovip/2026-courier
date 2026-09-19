import re

def patch_file(path, replacements):
    with open(path, "r") as f:
        content = f.read()
    if "_canonical_hash" not in content:
        content = "from scripts.integration_contract import _canonical_hash\n" + content
    for pattern, repl in replacements:
        content = re.sub(pattern, repl, content)
    with open(path, "w") as f:
        f.write(content)

patch_file("tests/test_zero_chat_motor_cannon.py", [
    (r'"result_id": f"res-\{tid\}",\n\s+"run_id": f"run-\{uuid\.uuid4\(\)\.hex\}"\n\s+\}', 
     r'"run_id": f"run-{uuid.uuid4().hex}",\n            "runtime_identity": task.get("server_binding")\n        }\n        identity = dict(payload)\n        identity.pop("raw_result", None)\n        payload["result_id"] = f"result-{_canonical_hash(identity)}"'),
    (r'"result_id": p\["result_id"\],', r'"result_id": payload["result_id"],')
])

patch_file("tests/test_turbo_queue.py", [
    (r'"result_id": "res_A2",\n\s+"status": "SUCCESS",\n\s+"artifacts": \[\]\n\s+\}',
     r'"status": "SUCCESS",\n            "artifacts": [],\n            "runtime_identity": t1.get("server_binding")\n        }\n        result_A["result_id"] = f"result-{_canonical_hash(result_A)}"'),
    (r'"result_id": "res_B2",\n\s+"status": "SUCCESS",\n\s+"artifacts": \[\]\n\s+\}',
     r'"status": "SUCCESS",\n            "artifacts": [],\n            "runtime_identity": t2.get("server_binding")\n        }\n        result_B["result_id"] = f"result-{_canonical_hash(result_B)}")
])

patch_file("tests/test_turbo_queue_concurrency.py", [
    (r'"result_id": "res_A",', r'"runtime_identity": t.get("server_binding"), "run_id": "run_1"'),
    (r'json=payload', r'json={**payload, "result_id": f"result-{_canonical_hash(payload)}" }')
])

