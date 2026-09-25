import re
from datetime import datetime

with open("tests/test_queue_independence.py", "r") as f:
    content = f.read()

now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

content = content.replace('"2026-09-18T22:05:45Z"', f'"{now_str}"')

with open("tests/test_queue_independence.py", "w") as f:
    f.write(content)
