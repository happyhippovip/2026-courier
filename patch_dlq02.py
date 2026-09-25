with open("tests/test_DLQ02_freshness_bound.py", "r") as f:
    content = f.read()

content = content.replace("ahl._attestation_resolver = dummy_resolver\nahl._verify_attestation = dummy_resolver", 
    "@pytest.fixture(autouse=True)\ndef apply_mock_resolver(monkeypatch):\n    monkeypatch.setattr(ahl, '_attestation_resolver', dummy_resolver)")

with open("tests/test_DLQ02_freshness_bound.py", "w") as f:
    f.write(content)
