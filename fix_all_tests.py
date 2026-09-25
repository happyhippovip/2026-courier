import os
import re
import glob

# 1. test_server_integration_contract.py:
with open("tests/test_server_integration_contract.py", "r") as f:
    text = f.read()

# Fix durable_result
text = text.replace('"execution_ref": "exec-" + uuid.uuid4().hex',
                    '"execution_ref": "exec-" + uuid.uuid4().hex,\n        "runtime_identity": task.get("server_binding")')

# Fix verification
text = text.replace('"artifacts": result["artifacts"],',
                    '"artifacts": result["artifacts"],\n        "received_runtime_identity": task.get("server_binding") or "MAC-01",')

with open("tests/test_server_integration_contract.py", "w") as f:
    f.write(text)

