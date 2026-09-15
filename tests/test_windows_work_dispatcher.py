import pytest
from pathlib import Path
from scripts.windows_work_dispatcher import WindowsWorkDispatcher

def test_windows_dispatcher_initialization():
    dispatcher = WindowsWorkDispatcher(repo_dir=Path.cwd())
    assert dispatcher.worker_id == "WINDOWS"
    assert dispatcher.remote_host == "DESKTOP-JDPRUGR"
    assert dispatcher.remote_user == "windows-ai"
