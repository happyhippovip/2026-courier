import re
with open("tests/test_server_integration_contract.py", "r") as f:
    text = f.read()

text = text.replace("assert http.post(\"/tasks/result\", headers=auth(), json=failed).status_code == 200", "r = http.post(\"/tasks/result\", headers=auth(), json=failed); print('BODY:', r.get_data(as_text=True)); assert r.status_code == 200")
with open("tests/test_server_integration_contract.py", "w") as f:
    f.write(text)
