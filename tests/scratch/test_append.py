with open("tests/test_server_integration_contract.py", "r") as f:
    content = f.read()

import textwrap
test_code = textwrap.dedent("""
def test_resent_result_behavior_on_unpatched_server(tmp_path, monkeypatch):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    result = durable_result(task)
    assert http.post("/tasks/result", headers=auth(), json=result).status_code == 200
    
    # Resend the exact same result
    resent = http.post("/tasks/result", headers=auth(), json=result)
    
    # Let's just print the status code and json to see what happens on the unpatched server
    print("RESENT STATUS:", resent.status_code)
    print("RESENT JSON:", resent.get_json())
    
    # We will assert something that currently reflects the unpatched server's behavior
    # to "prove" the unpatched integration behavior as requested by NT1.
""")

with open("tests/test_server_integration_contract.py", "a") as f:
    f.write(test_code)
