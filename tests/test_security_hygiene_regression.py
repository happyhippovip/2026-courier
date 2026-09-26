import os
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.app import app

def test_server_does_not_leak_bearer_token(tmp_path):
    # The server might hardcode debug_auth2.txt, so we'll check it and clean it up.
    if os.path.exists("debug_auth2.txt"):
        os.remove("debug_auth2.txt")
        
    app.config["TESTING"] = True
    client = app.test_client()
    
    # Send a request with a fake Bearer token
    secret_token = "secret_token_12345_do_not_leak"
    full_header = f"Bearer {secret_token}"
    response = client.get("/tasks/pending_verification", headers={"Authorization": full_header})
    
    assert response.status_code in (401, 403)
    
    # Check the current working directory for debug_auth2.txt
    leaked = False
    if os.path.exists("debug_auth2.txt"):
        with open("debug_auth2.txt", "r") as f:
            content = f.read()
            if secret_token in content:
                leaked = True
                
    assert not leaked, "CRITICAL: Server leaked the Bearer token to debug_auth2.txt!"


def test_auth_failure_attempts_no_file_write():
    """401 path must not attempt any debug file write (dead hardcoded path)."""
    app.config["TESTING"] = True
    client = app.test_client()
    opened = []
    real_open = open

    def spy(path, *args, **kwargs):
        opened.append(str(path))
        return real_open(path, *args, **kwargs)

    with mock.patch("builtins.open", side_effect=spy):
        response = client.get(
            "/workers", headers={"Authorization": "Bearer wrong-token"}
        )
    assert response.status_code == 401
    assert not [p for p in opened if "debug_auth2" in p], (
        f"auth failure attempted debug file writes: {opened}"
    )
