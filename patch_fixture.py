with open("tests/test_ledger_authenticated_receipts.py", "r") as f:
    content = f.read()

import_str = "import pytest\n"
if "import pytest" not in content:
    content = import_str + content

fixture_code = """
@pytest.fixture(autouse=True)
def restore_attestation_resolver():
    from scripts import agent_handoff_ledger
    old_resolver = agent_handoff_ledger._attestation_resolver
    yield
    agent_handoff_ledger._attestation_resolver = old_resolver
"""

# Insert fixture after imports
lines = content.split("\n")
insert_idx = 0
for i, line in enumerate(lines):
    if line.startswith("import ") or line.startswith("from "):
        insert_idx = i + 1

lines.insert(insert_idx, fixture_code)

with open("tests/test_ledger_authenticated_receipts.py", "w") as f:
    f.write("\n".join(lines))
