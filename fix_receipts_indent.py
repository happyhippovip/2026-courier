import re
with open("tests/test_ledger_authenticated_receipts.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "import pytest" in line:
        new_lines.append("from scripts.integration_contract import _canonical_hash\n")
    if "result.update(run_id='worker-process', result_id='res-1', status='SUCCESS', artifacts=[{'path':'a.txt','sha256':digest}])" in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(indent + "result.update(run_id='worker-process', status='SUCCESS', artifacts=[{'path':'a.txt','sha256':digest}])\n")
        new_lines.append(indent + "result['runtime_identity'] = task.get('server_binding')\n")
        new_lines.append(indent + "ident = {k:result[k] for k in ('goal_id','task_id','attempt_id','dispatch_id','execution_ref','worker_id','run_id','status','artifacts','runtime_identity')}\n")
        new_lines.append(indent + "result['result_id'] = f\"result-{_canonical_hash(ident)}\"\n")
    else:
        new_lines.append(line)

with open("tests/test_ledger_authenticated_receipts.py", "w") as f:
    f.writelines(new_lines)
