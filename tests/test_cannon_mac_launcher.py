"""No real server/browser in these bounded launcher unit tests."""
from unittest.mock import Mock

import pytest

from app.cannon import mac_launcher as launcher


def test_existing_cannon_only_opens_browser(monkeypatch):
    monkeypatch.setattr(launcher, "ready", lambda: True)
    popen = Mock(side_effect=AssertionError("No duplicate process"))
    run = Mock()
    monkeypatch.setattr(launcher.subprocess, "Popen", popen)
    monkeypatch.setattr(launcher.subprocess, "run", run)
    assert launcher.open_cannon() == 0
    run.assert_called_once_with(["/usr/bin/open", launcher.URL], check=True, timeout=10)


def test_first_open_detaches_server_and_ties_caffeinate_to_it(monkeypatch):
    monkeypatch.setattr(launcher, "ready", Mock(side_effect=[False, True]))
    server = Mock(pid=1234)
    popen = Mock(side_effect=[server, Mock()])
    run = Mock()
    monkeypatch.setattr(launcher.subprocess, "Popen", popen)
    monkeypatch.setattr(launcher.subprocess, "run", run)
    assert launcher.open_cannon() == 0
    first, second = popen.call_args_list
    assert first.args[0][-3:] == ["--cannon-only", "--port", "8768"]
    assert first.kwargs["start_new_session"] is True
    assert second.args[0] == ["/usr/bin/caffeinate", "-i", "-s", "-w", "1234"]
    server.wait.assert_not_called()
    run.assert_called_once()


def test_failed_start_never_opens_browser(monkeypatch):
    monkeypatch.setattr(launcher, "ready", lambda: False)
    server = Mock(pid=1234)
    server.poll.return_value = 1
    monkeypatch.setattr(launcher.subprocess, "Popen", Mock(return_value=server))
    run = Mock()
    monkeypatch.setattr(launcher.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="exited before HTTP"):
        launcher.open_cannon()
    run.assert_not_called()
