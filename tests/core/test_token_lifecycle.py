import os
import stat
from pathlib import Path
from courier_core.serve import load_or_create_token

def test_controller_token_lifecycle(tmp_path):
    token_path = tmp_path / "run" / "controller.token"
    
    # 1. Creation & Location
    token1 = load_or_create_token(token_path)
    assert token_path.exists(), "Token was not created at the expected location"
    assert len(token1) >= 32, "Token does not meet minimum length requirement"
    
    # 2. Permissions (0o600)
    # On Windows, os.chmod(0o600) might not behave the same, but the test can verify POSIX behavior if not Windows
    if os.name != "nt":
        st = os.stat(token_path)
        assert stat.S_IMODE(st.st_mode) == 0o600, f"Token file permissions are {oct(st.st_mode)}, expected 0o600"
        
    # 3. Reuse Rules & Restart Behavior
    # A subsequent call should load the exact same token instead of rotating it unnecessarily
    token2 = load_or_create_token(token_path)
    assert token1 == token2, "Token was incorrectly rotated on restart"
    
    # 4. Rotation / Cleanup of invalid tokens
    # If the token is corrupted or too short, it should be rotated
    token_path.write_text("invalid_short_token")
    token3 = load_or_create_token(token_path)
    assert token3 != "invalid_short_token", "Short/invalid token was not rotated"
    assert token3 != token1, "Token did not rotate to a new value"
    assert len(token3) >= 32, "Rotated token does not meet length requirement"
    
    # 5. Cleanup
    token_path.unlink()
    assert not token_path.exists(), "Cleanup failed"

