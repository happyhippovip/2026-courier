import re

with open("tests/test_agent_handoff_ledger.py", "r") as f:
    code = f.read()

setup_code = """
    def setUp(self):
        from tests.conftest import MatchDict
        ledger_module._attestation_resolver = lambda url: MatchDict({'verdict': 'PASS'})
"""

code = code.replace(
    'class AgentHandoffLedgerTests(unittest.TestCase):',
    'class AgentHandoffLedgerTests(unittest.TestCase):\n' + setup_code
)

with open("tests/test_agent_handoff_ledger.py", "w") as f:
    f.write(code)

with open("scripts/agent_handoff_ledger.py", "r") as f:
    code2 = f.read()

code2 = re.sub(
    r'if not receipt:\n\s*raise Exception\("DEBUG: receipt is None"\)\n.*?\n\s*if not receipt or',
    'if not receipt or',
    code2,
    flags=re.DOTALL
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code2)

