with open("tests/conftest.py", "r") as f:
    code = f.read()

import re
code = re.sub(r'@pytest\.fixture\(autouse=True\)\ndef _mock_attestation_for_all_tests.*', '', code, flags=re.DOTALL)

with open("tests/conftest.py", "w") as f:
    f.write(code)

with open("tests/test_ledger_authenticated_receipts.py", "r") as f:
    test_code = f.read()

test_code = "import os\nos.environ.pop('MOCK_LEDGER', None)\n" + test_code
with open("tests/test_ledger_authenticated_receipts.py", "w") as f:
    f.write(test_code)
