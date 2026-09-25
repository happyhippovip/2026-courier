import re
with open("tests/test_ledger_attestation_trust_root.py", "r") as f:
    content = f.read()

# Replace the previous mock_requests_get with _attestation_resolver
mock_fixture = """
import scripts.agent_handoff_ledger

@pytest.fixture(autouse=True)
def mock_resolver(monkeypatch):
    def fake_verify(url):
        if "distinct-pv" in url:
            producer = "prod-x"
            verifier = "ver-y"
        elif "cross-ver" in url:
            producer = "ext-prod"
            verifier = "colluding-ver"
        elif "independent" in url:
            producer = "real-prod"
            verifier = "real-ver"
        else:
            producer = "sys"
            verifier = "sys"

        return {
            "verdict": "PASS",
            "producer_principal": producer,
            "verifier_principal": verifier,
            "result_sha256": None,
            "goal_id": "trust-root-test",
            "binding": {
                "sha": "0000000000000000000000000000000000000000",
                "runtime": "TEST-RUNTIME-TRUST-ROOT"
            }
        }
    monkeypatch.setattr(scripts.agent_handoff_ledger, "_attestation_resolver", fake_verify)
"""

content = re.sub(r'import requests\n\n@pytest.fixture\(autouse=True\)\ndef mock_requests_get.*?return DummyResponse\(\)\n    monkeypatch.setattr\(requests, "get", fake_get\)\n', mock_fixture, content, flags=re.DOTALL)

with open("tests/test_ledger_attestation_trust_root.py", "w") as f:
    f.write(content)
