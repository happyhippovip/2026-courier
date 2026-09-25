import re
with open("tests/test_ledger_authenticated_receipts.py", "r") as f:
    content = f.read()

import_stmt = "from scripts.integration_contract import _canonical_hash\n"
if "_canonical_hash" not in content:
    content = content.replace("import pytest\n", "import pytest\n" + import_stmt)

replace_target = "result.update(run_id='worker-process', result_id='res-1', status='SUCCESS', artifacts=[{'path':'a.txt','sha256':digest}])"
replacement = """result.update(run_id='worker-process', status='SUCCESS', artifacts=[{'path':'a.txt','sha256':digest}])
        result['runtime_identity'] = task.get('server_binding')
        ident = {k:result[k] for k in ('goal_id','task_id','attempt_id','dispatch_id','execution_ref','worker_id','run_id','status','artifacts','runtime_identity')}
        result['result_id'] = f"result-{_canonical_hash(ident)}\""""

content = content.replace(replace_target, replacement)

with open("tests/test_ledger_authenticated_receipts.py", "w") as f:
    f.write(content)
