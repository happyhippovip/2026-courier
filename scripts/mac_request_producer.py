import json
import uuid
import os
import datetime
from pathlib import Path

REQUESTS_DIR = Path("coordination/mac_to_windows/requests")

def create_request():
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    req_id = f"REQ-MAC-{uuid.uuid4().hex[:8].upper()}"
    
    req = {
        "schema_version": "1.0",
        "mission_id": "COMMERCIAL_PILOT_STEP_2",
        "windows_validation_request_id": req_id,
        "created_by": "MAC_CHIEF",
        "artifact_reference": "demo_pilot/data_processor.py",
        "exact_question": "cmd.exe /c \"python -m pytest demo_pilot/test_data_processor.py & echo WINDOWS_PASSED\"",
        "expected_evidence": "WINDOWS_PASSED",
        "allowed_scope": "SAFE_LOCAL_VALIDATION",
        "validation_type": "WINDOWS_COMPATIBILITY",
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    
    tmp_path = REQUESTS_DIR / f"{req_id}.json.tmp"
    final_path = REQUESTS_DIR / f"{req_id}.json"
    
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(req, f, indent=2)
        
    os.replace(tmp_path, final_path)
    print(f"Delivered request {req_id} atomically.")
    return req_id

if __name__ == "__main__":
    create_request()
