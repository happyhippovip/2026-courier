"""Tests for pure-logic functions in scripts/run_content_production_pipeline.py.

Covers:
  - slugify
  - check_secrets_in_text
  - discover_godot_binary (with mocked filesystem)
"""

from pathlib import Path
import sys
from unittest.mock import patch, MagicMock

REPO = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO / "scripts"))

import run_content_production_pipeline as pipeline

def test_slugify():
    assert pipeline.slugify("Hello World!") == "hello-world"
    assert pipeline.slugify("---Test_Case---") == "test-case"
    assert pipeline.slugify("A"*100) == "a"*32
    assert pipeline.slugify("  Spaces   and ^%&* Symbols  ") == "spaces-and-symbols"

def test_check_secrets_in_text():
    assert pipeline.check_secrets_in_text("clean text with no secrets") == 0
    assert pipeline.check_secrets_in_text("Here is my secret: AKIAIOSFODNN7EXAMPLE") > 0
    assert pipeline.check_secrets_in_text("some -----BEGIN RSA PRIVATE KEY----- stuff") > 0
    assert pipeline.check_secrets_in_text("ghp_1234567890abcdef1234567890abcdef1234") > 0
    
@patch("os.path.exists")
@patch("subprocess.run")
def test_discover_godot_binary_found(mock_run, mock_exists):
    def mock_exists_impl(path):
        return path == "/Applications/Godot.app/Contents/MacOS/Godot"
        
    mock_exists.side_effect = mock_exists_impl
    
    mock_result = MagicMock()
    mock_result.stdout = "4.1.1.stable.official\n"
    mock_result.returncode = 0
    mock_run.return_value = mock_result
    
    bin_path, version = pipeline.discover_godot_binary()
    
    assert bin_path == "/Applications/Godot.app/Contents/MacOS/Godot"
    assert version == "4.1.1.stable.official"

@patch("os.path.exists")
def test_discover_godot_binary_not_found(mock_exists):
    mock_exists.return_value = False
    
    bin_path, version = pipeline.discover_godot_binary()
    assert bin_path is None
    assert version is None
