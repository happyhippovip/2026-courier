from courier_core.token_lifecycle import TokenManager
from courier_core.repository_hygiene import HygieneScanner
import os

def test_token_lifecycle(tmp_path):
    token_file = tmp_path / "controller.token"
    manager = TokenManager(str(token_file))
    
    # Generate
    token = manager.generate_and_store()
    assert os.path.exists(token_file)
    assert oct(os.stat(token_file).st_mode)[-3:] == "600"
    
    # Access & Verify
    assert manager.verify_request(f"Bearer {token}") is True
    assert manager.verify_request("Bearer fake") is False
    assert manager.verify_request("Basic auth") is False

def test_repository_hygiene(tmp_path):
    # Setup mock violation
    bad_file = tmp_path / "controller.token.bak"
    bad_file.write_text("bad")
    
    bad_dir = tmp_path / "__pycache__"
    bad_dir.mkdir()
    
    scanner = HygieneScanner()
    violations = scanner.scan(str(tmp_path))
    
    assert str(bad_file) in violations
    assert str(bad_dir) in violations
