import os
import re

for root, _, files in os.walk("tests"):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r") as f:
                code = f.read()
            
            # Simple replace for most cases
            # Match json={"task_id": ..., "verdict": ..., "verifier_id": ..., "result_id": ..., "artifacts": ...}
            # Since these are dictionary literals in strings, we can just replace "verdict": "PASS" with "verdict": "PASS", "received_runtime_identity": "test"
            
            if '"verdict": "PASS"' in code and '"received_runtime_identity"' not in code:
                code = code.replace('"verdict": "PASS"', '"verdict": "PASS", "received_runtime_identity": "test"')
                with open(path, "w") as f:
                    f.write(code)

