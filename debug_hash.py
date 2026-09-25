with open("tests/test_server_integration_contract.py", "r") as f:
    text = f.read()

text = text.replace('base["result_id"] = "result-" + _canonical_hash(ident)', 'print("MY_IDENT:", ident); base["result_id"] = "result-" + _canonical_hash(ident)')
with open("tests/test_server_integration_contract.py", "w") as f:
    f.write(text)
