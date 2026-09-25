import re
with open("tests/test_routing_acceptance_v1.py", "r") as f:
    content = f.read()

import_repl = """from server.app import SERVER_BINDING
def result_for(claimed, worker_id, result_id, status, stderr=None):"""

content = content.replace("def result_for(claimed, worker_id, result_id, status, stderr=None):", import_repl)

replacement = """        "result_id": result_id,
        "status": status,
        "runtime_identity": SERVER_BINDING,"""

content = content.replace("""        "result_id": result_id,
        "status": status,
        "runtime_identity": "TEST-RUNTIME",""", replacement)

with open("tests/test_routing_acceptance_v1.py", "w") as f:
    f.write(content)
