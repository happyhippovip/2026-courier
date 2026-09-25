with open("tests/test_server_integration_contract.py", "r") as f:
    text = f.read()

text = "from scripts.integration_contract import _canonical_hash\n" + text
with open("tests/test_server_integration_contract.py", "w") as f:
    f.write(text)
