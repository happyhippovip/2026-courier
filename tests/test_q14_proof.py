import pytest
import sys
import runpy
from pathlib import Path
from unittest.mock import patch

def test_q14_proof():
    # Insert repo root to sys.path
    repo_root = str(Path(__file__).resolve().parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    with patch("scripts.q14_proof.threading.Thread") as mock_thread, \
         patch("scripts.q14_proof.time.sleep"), \
         patch("scripts.q14_proof.urllib.request.urlopen") as mock_urlopen:
        
        # We need to simulate http_post responses
        # The script calls:
        # 1. /goals (Windows) -> None
        # 2. /goals (Linux) -> None
        # 3. /workers/register -> None
        # 4. /tasks/claim -> claim_lin
        # 5. /tasks/claim -> claim_lin2
        
        class MockResponse:
            def __init__(self, json_data, code=200):
                import json
                self.data = json.dumps(json_data).encode("utf-8")
                self.code = code
            def read(self):
                return self.data
            def getcode(self):
                return self.code
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        mock_urlopen.side_effect = [
            MockResponse({"status": "ok"}),  # 1
            MockResponse({"status": "ok"}),  # 2
            MockResponse({"status": "ok"}),  # 3
            MockResponse({"task": {"target_agent": "linux", "instruction": "Do linux task"}}),  # 4
            MockResponse({"task": None}),  # 5
        ]

        # Execute the script
        # We must prevent it from failing if `server_thread` is mocked
        # The script does:
        # server_thread = threading.Thread(...)
        # server_thread.start()
        # time.sleep(2)
        # http_post...
        
        runpy.run_path(str(Path(repo_root) / "scripts" / "q14_proof.py"), run_name="__main__")
        
        assert mock_urlopen.call_count == 5
