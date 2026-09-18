import sys
content = open("scripts/courier_continue.py").read()
content = content.replace(
'''def get_runtime_truth():
    import subprocess
    import os
    import json
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))''',
'''def get_runtime_truth():
    import subprocess
    import os
    import json
    if "MOCK_SHA" in os.environ:
        return os.environ["MOCK_SHA"]
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))''')
open("scripts/courier_continue.py", "w").write(content)
