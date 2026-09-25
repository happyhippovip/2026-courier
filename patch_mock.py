import os
from pathlib import Path

app_file = Path("server/app.py")
content = app_file.read_text()

content = content.replace('''"target_agent": "linux",
                    "instruction": f"touch mock_replenish_{count}.txt",''',
'''"target_agent": "linux",
                    "required_capabilities": ["mock-replenish-cap"],
                    "instruction": f"touch mock_replenish_{count}.txt",''')

app_file.write_text(content)

test_file = Path("tests/test_auto_replenishment.py")
test_content = test_file.read_text()
test_content = test_content.replace('''"capabilities": ["github-actions-safety-baseline-v1", "linux"]''',
'''"capabilities": ["github-actions-safety-baseline-v1", "linux", "mock-replenish-cap"]''')
test_file.write_text(test_content)
