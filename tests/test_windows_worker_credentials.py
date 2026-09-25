import importlib.util
from pathlib import Path

import pytest

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "windows_worker" / "daemon.py"
SOURCE = DAEMON_PATH.read_text(encoding="utf-8")


def load_daemon(monkeypatch):
    monkeypatch.delenv("COURIER_SERVER", raising=False)
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    spec = importlib.util.spec_from_file_location("windows_daemon_credentials", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    return daemon


def test_no_credential_or_server_constant_in_source():
    assert "API_KEY = \"" not in SOURCE
    assert "Bearer prod" not in SOURCE
    assert "192.168." not in SOURCE


def test_key_and_server_from_environment(monkeypatch):
    daemon = load_daemon(monkeypatch)
    monkeypatch.setenv("COURIER_SERVER", "http://env-host:8080/")
    monkeypatch.setenv("COURIER_API_KEY", "env-key-value")

    assert daemon.resolve_connection({}) == ("http://env-host:8080", "env-key-value")


def test_key_and_server_from_config(monkeypatch):
    daemon = load_daemon(monkeypatch)
    config = {"COURIER_SERVER": "http://cfg-host:8080", "COURIER_API_KEY": "cfg-key-value"}

    assert daemon.resolve_connection(config) == ("http://cfg-host:8080", "cfg-key-value")


def test_environment_overrides_config(monkeypatch):
    daemon = load_daemon(monkeypatch)
    monkeypatch.setenv("COURIER_SERVER", "http://env-host:8080")
    monkeypatch.setenv("COURIER_API_KEY", "env-key-value")
    config = {"COURIER_SERVER": "http://cfg-host:8080", "COURIER_API_KEY": "cfg-key-value"}

    assert daemon.resolve_connection(config) == ("http://env-host:8080", "env-key-value")


@pytest.mark.parametrize("config", [
    {"COURIER_SERVER": "http://cfg-host:8080"},
    {"COURIER_SERVER": "http://cfg-host:8080", "COURIER_API_KEY": "  "},
])
def test_missing_key_aborts_without_fallback(monkeypatch, config):
    daemon = load_daemon(monkeypatch)

    with pytest.raises(SystemExit, match="COURIER_API_KEY is not configured"):
        daemon.resolve_connection(config)


@pytest.mark.parametrize("server", [None, "", "local"])
def test_unconfigured_server_aborts(monkeypatch, server):
    daemon = load_daemon(monkeypatch)
    config = {"COURIER_API_KEY": "cfg-key-value"}
    if server is not None:
        config["COURIER_SERVER"] = server

    with pytest.raises(SystemExit, match="COURIER_SERVER is not configured") as raised:
        daemon.resolve_connection(config)
    assert "cfg-key-value" not in str(raised.value)


def test_startup_abort_happens_before_lock_and_never_leaks_key(monkeypatch, capsys):
    daemon = load_daemon(monkeypatch)
    monkeypatch.setattr(daemon, "load_config", lambda: {"WORKER_ID": "W", "COURIER_API_KEY": "cfg-key-value"})
    monkeypatch.setattr(daemon, "acquire_lock", lambda worker_id: pytest.fail("lock taken before config check"))

    with pytest.raises(SystemExit) as raised:
        daemon.loop()

    captured = capsys.readouterr()
    assert "cfg-key-value" not in str(raised.value) + captured.out + captured.err
