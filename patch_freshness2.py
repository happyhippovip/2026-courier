import re
with open("tests/test_ledger_freshness_binding_epoch.py", "r") as f:
    content = f.read()

replacement = """def mock_resolver(url):
    print("MOCK RESOLVER CALLED WITH URL", url)
    return {
        "verdict": "PASS",
        "producer_principal": "prod-ext",
        "verifier_principal": "ver-ext",
        "result_sha256": "fake-hash",
        "goal_id": "freshness-test",
        "binding": {"sha": SHA, "runtime": RUNTIME}
    }
ahl._attestation_resolver = mock_resolver"""

content = re.sub(r'def mock_resolver\(url\):.*?ahl\._attestation_resolver = mock_resolver', replacement, content, flags=re.DOTALL)

with open("tests/test_ledger_freshness_binding_epoch.py", "w") as f:
    f.write(content)
