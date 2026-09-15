from pathlib import Path
import re

p = Path("scripts/mac_result_consumer.py")
code = p.read_text()

pattern = r'            if not \(REQUESTS_DIR / f"\{req_id\}\.json"\)\.exists\(\) and not \(Path\("coordination/mac_to_windows/archive"\) / f"\{req_id\}\.json"\)\.exists\(\):'
replacement = r'            if not (REQUESTS_DIR / f"{req_id}.json").exists() and not (Path("coordination/mac_to_windows/archive") / f"{req_id}.json").exists() and not (Path("coordination/local_requests") / f"{req_id}.json").exists():'

code = re.sub(pattern, replacement, code)
p.write_text(code)
print("Patched request lookup.")
