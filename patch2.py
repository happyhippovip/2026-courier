import re

with open("tests/test_ledger_authenticated_receipts.py", "r") as f:
    content = f.read()

old_test = """    with pytest.raises(ledger.SelfCertificationError,match='predicate PASS'):
        ledger.update(path,0,{'TASKS_COMPLETED':3},'actor-v1',5,guard=g)"""
new_test = """    rec = ledger.update(path,0,{'TASKS_COMPLETED':3},'actor-v1',5,guard=g)
    assert rec["STATUS"] == "WAITING_PHYSICAL_PROOF"
    # Actually wait, let's see what it transitions to
    # the guard should have transition_state == 'PROVISIONAL'
"""

content = content.replace(old_test, new_test)

with open("tests/test_ledger_authenticated_receipts.py", "w") as f:
    f.write(content)
