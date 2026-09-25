with open("tests/test_ledger_authenticated_receipts.py", "r") as f:
    content = f.read()

# Replace the fixture we added earlier
old_fixture = """
@pytest.fixture(autouse=True)
def restore_attestation_resolver():
    from scripts import agent_handoff_ledger
    old_resolver = agent_handoff_ledger._attestation_resolver
    yield
    agent_handoff_ledger._attestation_resolver = old_resolver
"""
new_fixture = ""
content = content.replace(old_fixture, new_fixture)

# Update setup_ledger to use monkeypatch
# Wait, setup_ledger is just a function. We can just add monkeypatch to setup_ledger?
# We can't easily add monkeypatch to setup_ledger without modifying all calls.
# Better to just use monkeypatch in a fixture in test_ledger_authenticated_receipts.py to restore it.

fixture2 = """
@pytest.fixture(autouse=True)
def restore_resolver():
    from scripts import agent_handoff_ledger
    original = agent_handoff_ledger._attestation_resolver
    yield
    agent_handoff_ledger._attestation_resolver = original
"""
content = content.replace("import pytest\n", "import pytest\n" + fixture2)

with open("tests/test_ledger_authenticated_receipts.py", "w") as f:
    f.write(content)
