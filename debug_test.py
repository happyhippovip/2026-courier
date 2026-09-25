import pytest
import sys
import scripts.agent_handoff_ledger as hl

original_verify = hl._verify_attestation
def noisy_verify(url):
    print(f"DEBUG: VERIFY ATTESTATION {url}")
    res = original_verify(url)
    print(f"DEBUG: VERIFY RESULT {res}")
    return res

hl._verify_attestation = noisy_verify

pytest.main(["-v", "-s", "tests/test_ledger_attestation_trust_root.py::TestProducerEqualsVerifier::test_independent_writer_with_distinct_prod_ver_succeeds"])
