from scripts.mac_result_consumer import verify_fingerprint
import hashlib
import json

def test_compatibility():
    # A. current real Windows result schema -> accepted
    evidence_content = "EXIT_0_WITH_OBSERVED_LOCAL_EFFECT"
    windows_res = {
        "windows_validation_request_id": "TEST-1",
        "status": "PASS",
        "content_integrity": "SHA256:" + hashlib.sha256(evidence_content.encode()).hexdigest(),
        "evidence_content": evidence_content,
    }
    assert verify_fingerprint(windows_res) == True

    # B. valid legacy/current Mac-supported schema -> accepted
    mac_req = "TEST-2"
    mac_status = "COMPLETED"
    mac_obs = "OBS"
    mac_calc = hashlib.sha256(f"{mac_req}{mac_status}{mac_obs}".encode("utf-8")).hexdigest()
    mac_res = {
        "request_id": mac_req,
        "status": mac_status,
        "observed_behavior": mac_obs,
        "result_fingerprint": mac_calc
    }
    assert verify_fingerprint(mac_res) == True

    # C. missing identity -> rejected
    # In consumer, this skips file processing before verify_fingerprint
    # But verify_fingerprint should also reject missing hashes
    assert verify_fingerprint({}) == False

    # D. malformed/wrong fingerprint/integrity -> rejected
    bad_windows = {
        "windows_validation_request_id": "TEST-1",
        "content_integrity": "SHA256:" + hashlib.sha256(b"expected").hexdigest(),
        "evidence_content": "different"
    }
    assert verify_fingerprint(bad_windows) == False

    bad_mac = mac_res.copy()
    bad_mac["result_fingerprint"] = "bad"
    assert verify_fingerprint(bad_mac) == False

if __name__ == "__main__":
    test_compatibility()
    print("ALL TESTS PASSED")
