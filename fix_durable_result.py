with open("tests/test_server_integration_contract.py", "r") as f:
    text = f.read()

text = text.replace('"execution_ref": "exec-" + uuid.uuid4().hex', '"execution_ref": "exec-" + uuid.uuid4().hex,\n        "runtime_identity": "MAC-01"')
with open("tests/test_server_integration_contract.py", "w") as f:
    f.write(text)
