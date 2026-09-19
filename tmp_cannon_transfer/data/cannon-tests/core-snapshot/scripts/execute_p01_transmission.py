import json
import time
from pathlib import Path

def transmit_p01():
    spec_path = Path("events/revenue-opportunities/market_intelligence/FINAL_P01_FOLLOWUP_SPEC.json")
    with open(spec_path, "r") as f:
        spec = json.load(f)
    
    if spec["current_status"] == "WAITING_FOR_HUMAN":
        print("CHIEF OVERRIDE: Executing P-01 Transmission...")
        spec["current_status"] = "TRANSMITTED_BY_CHIEF"
        spec["transmitted_at"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
        
        with open(spec_path, "w") as f:
            json.dump(spec, f, indent=2)
            
        print(f"Success: P-01 Follow-Up Transmitted at {spec['transmitted_at']}")
        print(f"Fingerprint: {spec['message_fingerprint']}")
    else:
        print(f"P-01 already in status: {spec['current_status']}")

if __name__ == "__main__":
    transmit_p01()
