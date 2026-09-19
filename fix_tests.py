import os
import re

for root, _, files in os.walk("tests"):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r") as f:
                content = f.read()

            if "result_id" in content and "artifacts" in content:
                # Add import if _canonical_hash is not there
                if "_canonical_hash" not in content:
                    content = "from scripts.integration_contract import _canonical_hash\n" + content

                # In complete() helper in zero_chat_motor_cannon
                content = re.sub(
                    r'("run_id": [^\n]+)\n\s+}',
                    r'\1,\n            "runtime_identity": task.get("server_binding")\n        }\n        identity = dict(payload)\n        identity.pop("raw_result", None)\n        payload["result_id"] = f"result-{_canonical_hash(identity)}"',
                    content
                )
                
                # In test_turbo_queue integration test
                content = re.sub(
                    r'("result_id": "res_A2",\n\s+"status": "SUCCESS",\n\s+"artifacts": \[\])',
                    r'"status": "SUCCESS",\n            "artifacts": [],\n            "runtime_identity": t1.get("server_binding")\n        }\n        result_A["result_id"] = f"result-{_canonical_hash(result_A)}"',
                    content
                )
                content = re.sub(
                    r'("result_id": "res_B2",\n\s+"status": "SUCCESS",\n\s+"artifacts": \[\])',
                    r'"status": "SUCCESS",\n            "artifacts": [],\n            "runtime_identity": t2.get("server_binding")\n        }\n        result_B["result_id"] = f"result-{_canonical_hash(result_B)}"',
                    content
                )
                
                # ... and other manual payloads. This might be fragile. Let's see if we can just monkeypatch _canonical_hash in the tests where we don't care!
                pass
