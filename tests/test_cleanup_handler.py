import pytest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import cleanup_handler

def test_release_execution_resources(capsys):
    cleanup_handler.release_execution_resources("exec_001")
    captured = capsys.readouterr()
    assert "Releasing resources for execution: exec_001" in captured.out
    assert "Cleanup for exec_001 complete." in captured.out

