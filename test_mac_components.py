import json, os, time
from scripts.mac_heartbeat_producer import atomic_write, HEARTBEAT_PATH
from scripts.mac_request_producer import create_request, REQUESTS_DIR
from scripts.mac_result_consumer import verify_fingerprint, consume_results, RESULTS_DIR, ACKS_DIR

def test():
    # 1. Heartbeat write
    atomic_write(HEARTBEAT_PATH, {"test": "hb"})
    assert HEARTBEAT_PATH.exists()
    
    # 2. Request
    req_id = create_request()
    assert (REQUESTS_DIR / f"{req_id}.json").exists()
    
    # 3. Result Consumer (fail closed on missing fingerprint)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    res_id = "RES-TEST-1"
    bad_res = {"request_id": req_id, "schema_version": "1.0", "result_fingerprint": "bad"}
    with open(RESULTS_DIR / f"{res_id}.json", "w") as f:
        json.dump(bad_res, f)
    consume_results()
    assert not (ACKS_DIR / f"{req_id}.ack.json").exists()
    
    # 4. Result Consumer (success & deduplication)
    good_res = {
        "request_id": req_id,
        "schema_version": "1.0",
        "status": "PASS",
        "observed_behavior": "tested"
    }
    import hashlib
    fingerprint = hashlib.sha256(f"{req_id}PASStested".encode("utf-8")).hexdigest()
    good_res["result_fingerprint"] = fingerprint
    with open(RESULTS_DIR / f"{res_id}.json", "w") as f:
        json.dump(good_res, f)
    
    consume_results()
    assert (ACKS_DIR / f"{req_id}.ack.json").exists()
    
    # run again to ensure no error on duplicate
    consume_results()
    
    print("ALL TARGETED TESTS PASSED")

if __name__ == "__main__":
    test()
