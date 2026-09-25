"""Targeted test: windows daemon takes server auth from env/config, never source.

- No credential literals may remain in daemon.py source.
- init_server_auth prefers env, falls back to bootstrap-populated config,
  and fails closed when either value is absent.
"""
import importlib.util
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
DAEMON_PATH = REPO_ROOT / "scripts" / "windows_worker" / "daemon.py"


def load_daemon():
    spec = importlib.util.spec_from_file_location("windows_daemon", DAEMON_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_credential_literals_in_source():
    source = DAEMON_PATH.read_text()
    assert "prod-secret" not in source
    assert "192.168.178.162" not in source
    assert not re.search(r'API_KEY\s*=\s*"[^"]+"', source)


def test_init_from_config(monkeypatch):
    daemon = load_daemon()
    monkeypatch.delenv("COURIER_SERVER", raising=False)
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    url = daemon.init_server_auth({"COURIER_SERVER": "https://srv:8080/",
                                   "COURIER_API_KEY": "k"})
    assert url == "https://srv:8080"
    assert daemon.HEADERS["Authorization"] == "Bearer k"


def test_env_overrides_config(monkeypatch):
    daemon = load_daemon()
    monkeypatch.setenv("COURIER_SERVER", "https://env:9090")
    monkeypatch.setenv("COURIER_API_KEY", "env-key")
    url = daemon.init_server_auth({"COURIER_SERVER": "https://cfg:8080",
                                   "COURIER_API_KEY": "cfg-key"})
    assert url == "https://env:9090"
    assert daemon.HEADERS["Authorization"] == "Bearer env-key"


def test_missing_auth_fails_closed(monkeypatch):
    daemon = load_daemon()
    monkeypatch.delenv("COURIER_SERVER", raising=False)
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        daemon.init_server_auth({})
