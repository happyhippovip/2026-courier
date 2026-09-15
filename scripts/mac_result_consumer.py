import json
import os
import time
import hashlib
import uuid
from pathlib import Path

RESULTS_DIR = Path("coordination/windows_to_mac/results")
ACKS_DIR = Path("coordination/mac_to_windows/acks")
REQUESTS_DIR = Path("coordination/mac_to_windows/requests")

def verify_fingerprint(result_data: dict) -> bool:
    # Contract: sha256(request_id + status + observed_behavior)
    expected = result_data.get("result_fingerprint")
    if expected:
        req_id = result_data.get("request_id", "")
        status = result_data.get("status", "")
        obs = result_data.get("observed_behavior", "")
        calc = hashlib.sha256(f"{req_id}{status}{obs}".encode("utf-8")).hexdigest()
        return calc == expected
        
    # Windows schema: recompute the declared digest from independently read
    # evidence content. Merely echoing the digest in an evidence string is not
    # proof of an effect.
    ci = result_data.get("content_integrity")
    if ci and ci.startswith("SHA256:"):
        evidence_content = result_data.get("evidence_content")
        if not isinstance(evidence_content, str) or not evidence_content:
            return False
        declared = ci[len("SHA256:"):]
        return hashlib.sha256(evidence_content.encode("utf-8")).hexdigest() == declared
    
    return False

def consume_results():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ACKS_DIR.mkdir(parents=True, exist_ok=True)
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    
    results = list(RESULTS_DIR.glob("*.json"))
    for res_file in results:
        try:
            with open(res_file, "r") as f:
                data = json.load(f)
                
            req_id = data.get("request_id") or data.get("windows_validation_request_id")
            if not req_id or not isinstance(req_id, str):
                continue
                
            # SANITIZE path traversal
            if "/" in req_id or "\\" in req_id or ".." in req_id or "\0" in req_id:
                print(f"Rejecting result for {req_id}: Malformed or unauthorized request ID.")
                continue
                
            if not (REQUESTS_DIR / f"{req_id}.json").exists() and not (Path("coordination/mac_to_windows/archive") / f"{req_id}.json").exists() and not (Path("coordination/local_requests") / f"{req_id}.json").exists():
                print(f"Rejecting result for {req_id}: Original request not found.")
                continue
                
            ack_file = ACKS_DIR / f"{req_id}.ack.json"
            print(f"Discovered result for {req_id}")
            
            # Verify Independent Customs
            if not data.get("schema_version"):
                print("Missing schema_version, rejecting")
                continue
                
            if not verify_fingerprint(data):
                print("FINGERPRINT INVALID")
                continue

            if ack_file.exists():
                print(f"Result for {req_id} verified OK; ACK already exists — idempotent skip.")
                continue
                
            # Write Ack
            ack = {
                "request_id": req_id,
                "result_id": data.get("result_id", "unknown"),
                "fingerprint": data.get("result_fingerprint") or data.get("content_integrity"),
                "timestamp": time.time(),
                "state": "RESULT_CONSUMED, RESULT_VERIFIED, RESULT_ACKNOWLEDGED"
            }
            
            tmp = ack_file.with_suffix(f".tmp.{os.getpid()}.{uuid.uuid4().hex}")
            with open(tmp, "w") as f:
                json.dump(ack, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, ack_file)
            print(f"Successfully verified and acknowledged result for {req_id}")
            
        except Exception as e:
            print(f"Error processing {res_file}: {e}")

if __name__ == "__main__":
    consume_results()
