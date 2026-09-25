with open("tests/test_server_integration_contract.py", "r") as f:
    text = f.read()

text = text.replace('"execution_ref": task.get("execution_ref", "exec-mock"),',
                    '"execution_ref": task.get("execution_ref", "exec-mock"),\n        "runtime_identity": task.get("server_binding"),')
with open("tests/test_server_integration_contract.py", "w") as f:
    f.write(text)
