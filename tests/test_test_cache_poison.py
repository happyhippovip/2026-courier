import os
import runpy
from pathlib import Path

def test_cache_poison_execution(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    
    script_path = Path(__file__).parent.parent / "scripts" / "test_cache_poison.py"
    
    # Run the script
    runpy.run_path(str(script_path))
    
    # Verify it created what it should have
    assert (tmp_path / "poison_test.py").exists()
    
    # The printed output is not easy to capture without capsys, but the runpy execution
    # should not raise any exceptions and complete successfully.
    assert True
