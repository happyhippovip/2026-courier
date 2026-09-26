with open("tests/test_server_integration_contract.py", "r") as f:
    lines = f.readlines()

new_lines = []
in_test = False
for line in lines:
    if line.startswith("def test_resent_result_behavior_on_unpatched_server"):
        in_test = True
    if in_test and line.strip() == "":
        pass # allow empty lines
    if in_test and line.startswith("def "):
        in_test = False
    
    if not in_test:
        new_lines.append(line)

# Now we append the proper test
import textwrap
test_code = textwrap.dedent("""
def test_resent_result_is_ignored_on_unpatched_server(tmp_path, monkeypatch):
    '''Proves the unpatched server's behavior on duplicate result (NT1).
    The patched server returns ACK_DUPLICATE, while the live server returns IGNORED.
    '''
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    result = durable_result(task)
    assert http.post("/tasks/result", headers=auth(), json=result).status_code == 200
    
    resent = http.post("/tasks/result", headers=auth(), json=result)
    assert resent.status_code == 200
    data = resent.get_json()
    assert data["status"] == "IGNORED"
    assert data["reason"] == "DUPLICATE_OR_ALREADY_PROCESSED"
""")
new_lines.append(test_code)

with open("tests/test_server_integration_contract.py", "w") as f:
    f.writelines(new_lines)
