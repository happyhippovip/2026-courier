import re
with open("tests/test_DLQ02_freshness_bound.py", "r") as f:
    code = f.read()

# I need to add monkeypatch parameter to both test functions
code = code.replace("def test_dlq02_stale_evidence_rejected(tmp_path):", "def test_dlq02_stale_evidence_rejected(tmp_path, monkeypatch):")
code = code.replace("def test_dlq02_fresh_evidence_accepted(tmp_path):", "def test_dlq02_fresh_evidence_accepted(tmp_path, monkeypatch):")

# I need to define the mock inside the test file and monkeypatch it
mock_code = """
def patch_verify(monkeypatch):
    def fake_verify(url: str):
        return {
            "verdict": "PASS",
            "result_sha256": "0000000000000000000000000000000000000000",
            "producer_principal": "producer_1",
            "verifier_principal": "verifier_1",
            "binding": {
                "sha": base_guard()["binding"]["current_sha"],
                "runtime": base_guard()["binding"]["runtime_identity"]
            },
            "goal_id": base_record()["GOAL"]
        }
    monkeypatch.setattr(ahl, "_verify_attestation", fake_verify)

def test_dlq02_stale_evidence_rejected(tmp_path, monkeypatch):
    patch_verify(monkeypatch)"""

code = code.replace("def test_dlq02_stale_evidence_rejected(tmp_path, monkeypatch):", mock_code)

mock_code2 = """
def test_dlq02_fresh_evidence_accepted(tmp_path, monkeypatch):
    patch_verify(monkeypatch)"""
code = code.replace("def test_dlq02_fresh_evidence_accepted(tmp_path, monkeypatch):", mock_code2)

with open("tests/test_DLQ02_freshness_bound.py", "w") as f:
    f.write(code)
