import pytest
from pathlib import Path
from app.cannon.adapters import LiveMuseAdapter

def test_windows_paths_in_canary_validation():
    # Simulate a path on Windows
    expected_path = Path("C:/Users/test/workspace/nonce.txt")
    
    # Muse returns it with backslashes and different case
    result_path = "c:\\users\\TEST\\workspace\\nonce.txt"
    nonce = "1234"
    sha = "abcd"
    
    events = [
        {
            "payload_type": "run.terminal.completed",
            "payload": {
                "terminal": "completed",
                "text": f'{{"path": "{result_path.replace(chr(92), chr(92)*2)}", "nonce": "{nonce}", "sha256": "{sha}"}}'
            }
        }
    ]
    
    # This should succeed if paths are normalized, but will raise WRONG_CANARY_RESULT currently
    LiveMuseAdapter.validate_canary_terminal(events, expected_path, nonce, sha)

