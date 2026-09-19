with open("tests/test_ledger_authenticated_receipts.py", "r") as f:
    code = f.read()

# Replace the resolver logic in the test to return the JSON instead of bool
new_setup = """def setup_ledger(context, e):
    from scripts import agent_handoff_ledger
    def resolve(url):
        path = url.replace('https://courier.test', '')
        resp = context['http'].get(path, headers={'Authorization': 'Bearer test-secret'})
        if resp.status_code != 200: return None
        return resp.json
    agent_handoff_ledger._attestation_resolver = resolve

    path = context['tmp'] / 'ledger.json'"""

import re
code = re.sub(
    r'def setup_ledger\(context, e\):\n    from scripts import agent_handoff_ledger\n    def resolve\(url, expected_sha\):.*?agent_handoff_ledger\._attestation_resolver = resolve\n\n    path = context\[\'tmp\'\] / \'ledger\.json\'',
    new_setup,
    code,
    flags=re.DOTALL
)

with open("tests/test_ledger_authenticated_receipts.py", "w") as f:
    f.write(code)
