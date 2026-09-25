from pathlib import Path
p = Path("tests/test_p6_economics.py")
content = p.read_text()

start = content.find("    # Submit result with cost 6.00")
end = content.find("    assert resp.status_code == 200") + len("    assert resp.status_code == 200\n")

repl = """    # Submit result with cost 6.00
    from tests.test_server_integration_contract import _create_valid_result
    payload = _create_valid_result(task)
    payload["actual_cost"] = 6.00
    resp = client.post("/tasks/result", headers=auth(), json=payload)
    assert resp.status_code == 200
"""

content = content[:start] + repl + content[end:]
p.write_text(content)
