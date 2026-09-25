import re
with open("tests/test_server_integration_contract.py", "r") as f:
    text = f.read()

text = text.replace('hashlib.sha256(b"bounded\n").hexdigest()', 'hashlib.sha256(b"bounded\\n").hexdigest()')

with open("tests/test_server_integration_contract.py", "w") as f:
    f.write(text)
