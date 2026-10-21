import json
import sys
from pathlib import Path

def transmit_p01():
    spec_path = Path("events/revenue-opportunities/market_intelligence/FINAL_P01_FOLLOWUP_SPEC.json")
    with open(spec_path, "r") as f:
        spec = json.load(f)

    status = spec.get("current_status")
    print(f"P-01 was not transmitted. No delivery was recorded. Status remains {status}.")
    return 1

if __name__ == "__main__":
    sys.exit(transmit_p01())
