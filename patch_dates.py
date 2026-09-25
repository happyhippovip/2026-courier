import re
from datetime import datetime
import glob

now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

for filename in glob.glob("tests/*.py"):
    with open(filename, "r") as f:
        content = f.read()
    
    if "2026-09-18" in content:
        content = re.sub(r'"2026-09-18T\d{2}:\d{2}:\d{2}Z"', f'"{now_str}"', content)
        with open(filename, "w") as f:
            f.write(content)
