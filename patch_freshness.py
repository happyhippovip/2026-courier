with open("tests/test_ledger_freshness_binding_epoch.py", "r") as f:
    content = f.read()

content = content.replace("ahl._attestation_resolver = mock_resolver", 
    "@pytest.fixture(autouse=True)\ndef apply_mock_resolver(monkeypatch):\n    monkeypatch.setattr(ahl, '_attestation_resolver', mock_resolver)")

with open("tests/test_ledger_freshness_binding_epoch.py", "w") as f:
    f.write(content)
