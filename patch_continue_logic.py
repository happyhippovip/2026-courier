import re

with open("scripts/courier_continue.py", "r") as f:
    content = f.read()

# Remove the 'continue' from 'if not safe_executable_tasks' block
old_block = '''            if "MOCK_SHA" in os.environ:
                mock_iters += 1
                if mock_iters >= 10:
                    sys.exit(0)
            import time
            time.sleep(0.1 if 'MOCK_SHA' in os.environ else 1.0)
            continue'''

new_block = '''            if "MOCK_SHA" in os.environ:
                if not running_tasks:
                    mock_iters += 1
                    if mock_iters >= 10:
                        sys.exit(0)
                else:
                    mock_iters = 0
            import time
            time.sleep(0.1 if 'MOCK_SHA' in os.environ else 1.0)'''

content = content.replace(old_block, new_block)

with open("scripts/courier_continue.py", "w") as f:
    f.write(content)
