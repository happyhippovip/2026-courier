import pytest
import os
import json
from pathlib import Path
import hashlib
import time

def test_mac_result_consumer_traversal(tmp_path):
    os.chdir(tmp_path)
    from scripts.mac_result_consumer import consume_results, RESULTS_DIR, REQUESTS_DIR, ACKS_DIR
    
    # We want to write an ACK to a malicious path.
    # Suppose we manage to get a request created at `../../malicious`
    # Let's create the directories so we can simulate it
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    ACKS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Malicious request ID
    malicious_req = "../malicious"
    
    # Create the original request
    req_file = REQUESTS_DIR / f"{malicious_req}.json"
    req_file.parent.mkdir(parents=True, exist_ok=True)
    req_file.touch()
    
    # Create result
    obs = "test"
    status = "PASS"
    calc = hashlib.sha256(f"{malicious_req}{status}{obs}".encode("utf-8")).hexdigest()
    
    res = {
        "request_id": malicious_req,
        "status": status,
        "observed_behavior": obs,
        "schema_version": "v1",
        "result_fingerprint": calc
    }
    with open(RESULTS_DIR / "res.json", "w") as f:
        json.dump(res, f)
        
    consume_results()
    
    # Did it traverse and write?
    assert not (ACKS_DIR / f"{malicious_req}.ack.json").exists(), "Path traversal allowed!"

