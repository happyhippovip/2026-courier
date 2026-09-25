import re
with open("tests/test_ledger_freshness_binding_epoch.py", "r") as f:
    content = f.read()

replacement = """from scripts.agent_handoff_ledger import (
    initialize, update, validate_guard, LedgerError,
)
import scripts.agent_handoff_ledger as ahl

def mock_resolver(url):
    print("MOCK RESOLVER CALLED", url)
    return {
        "verdict": "PASS",
        "producer_principal": "prod-ext",
        "verifier_principal": "ver-ext",
        "result_sha256": "fake-hash",
        "goal_id": "freshness-test",
        "binding": {"sha": SHA, "runtime": RUNTIME}
    }
ahl._attestation_resolver = mock_resolver
"""

content = content.replace("""from scripts.agent_handoff_ledger import (
    initialize, update, validate_guard, LedgerError,
)""", replacement)

with open("tests/test_ledger_freshness_binding_epoch.py", "w") as f:
    f.write(content)
