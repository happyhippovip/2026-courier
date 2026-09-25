from pathlib import Path
import re

p = Path("tests/test_p6_economics.py")
content = p.read_text()

repl = """    from tests.test_server_integration_contract import _create_valid_result
    payload = _create_valid_result(task)
    payload["actual_cost"] = 6.00
    
    resp = client.post("/tasks/result", headers=auth(), json=payload)"""

content = re.sub(
    r'        payload = dict\(task\).*?resp = client.post\("/tasks/result", headers=auth\(\), json=payload\)',
    repl,
    content,
    flags=re.DOTALL
)
p.write_text(content)
