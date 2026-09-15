import json, sys
from pathlib import Path
res_file = Path("coordination/windows_to_mac/results/REQ-MAC-15dc6589.json")
data = json.load(open(res_file))
req_id = data.get("request_id")
print("req_id:", req_id)
req_file = Path("coordination/mac_to_windows/requests") / f"{req_id}.json"
print("req_file exists:", req_file.exists())
