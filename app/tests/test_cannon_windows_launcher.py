"""Unit tests for Windows Cannon launcher."""
from unittest.mock import Mock
import pytest

from app.cannon import windows_launcher as launcher


def test_existing_cannon_only_opens_browser(monkeypatch):
    monkeypatch.setattr(launcher, "ready", lambda: True)
    popen = Mock(side_effect=AssertionError("No duplicate process"))
    browser = Mock()
    monkeypatch.setattr(launcher.subprocess, "Popen", popen)
    monkeypatch.setattr(launcher, "open_browser", browser)
    assert launcher.open_cannon() == 0
    browser.assert_called_once_with(launcher.URL)


def test_first_open_detaches_server_and_polls_readiness(monkeypatch):
    monkeypatch.setattr(launcher, "ready", Mock(side_effect=[False, True]))
    server = Mock(pid=5678, poll=Mock(return_value=None))
    popen = Mock(return_value=server)
    browser = Mock()
    monkeypatch.setattr(launcher.subprocess, "Popen", popen)
    monkeypatch.setattr(launcher, "open_browser", browser)
    assert launcher.open_cannon() == 0
    popen.assert_called_once()
    args, kwargs = popen.call_args
    assert args[0][-3:] == ["--cannon-only", "--port", "8768"]
    if launcher.sys.platform == "win32":
        assert "creationflags" in kwargs
    else:
        assert kwargs.get("start_new_session") is True
    browser.assert_called_once_with(launcher.URL)


def test_failed_start_never_opens_browser(monkeypatch):
    monkeypatch.setattr(launcher, "ready", lambda: False)
    server = Mock(pid=5678, poll=Mock(return_value=1))
    monkeypatch.setattr(launcher.subprocess, "Popen", Mock(return_value=server))
    browser = Mock()
    monkeypatch.setattr(launcher, "open_browser", browser)
    with pytest.raises(RuntimeError, match="exited before HTTP"):
        launcher.open_cannon()
    browser.assert_not_called()


def test_launch_lock_lifecycle(tmp_path):
    lock_file_path = tmp_path / "test-cannon-launch.lock"
    with lock_file_path.open("a+b") as lock1:
        launcher.acquire_launch_lock(lock1)
        launcher.release_launch_lock(lock1)
