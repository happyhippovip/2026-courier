from pathlib import Path
import re

adapters_path = Path("scripts/courier_real_worker_adapters.py")
code = adapters_path.read_text()

pattern = r'"STATUS": "PENDING"\n        \}'
replacement = '"STATUS": "PENDING",\n            "SCRIPT": payload_in.get("prompt", "") or payload_in.get("action", "") or ""\n        }'

if re.search(pattern, code):
    code = re.sub(pattern, replacement, code)
    adapters_path.write_text(code)
    print("Fixed!")
else:
    print("Not found")
