import os
from pathlib import Path

test_file = Path("tests/test_global_queue_stall.py")
content = test_file.read_text()
content = content.replace('"capabilities": ["linux"]}', '"capabilities": ["linux"], "provider": "openai"}')
test_file.write_text(content)
