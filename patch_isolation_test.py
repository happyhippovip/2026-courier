import os
from pathlib import Path

test_file = Path("tests/test_provider_wait_isolation.py")
content = test_file.read_text()

content = content.replace('state["provider_locks"]["pool-A:openai"] = time.time() - 10', '''state["provider_locks"]["pool-A:openai"] = time.time() - 10
                state["tasks"]["task-1"]["next_retry_at"] = time.time() - 10''')
test_file.write_text(content)
