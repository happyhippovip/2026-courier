"""Secret hygiene for the Mac worker daemon: keys must never reach logs."""

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "scripts" / "mac_worker"
TRACKED_CONFIG = SCRIPTS / "config.json"
KEYCHAIN_SETUP = SCRIPTS / "setup_keychain.sh"
FAKE_KEY = "TEST-FAKE-KEY-0123456789abcdef"


def load_daemon(monkeypatch, tmp_path, key=FAKE_KEY, keychain_key=None, config_key=None):
    cfg = tmp_path / "cfg.json"
    config = {"WORKER_ID": "t", "COURIER_SERVER": "http://127.0.0.1:9/"}
    if config_key is not None:
        config["COURIER_API_KEY"] = config_key
    cfg.write_text(json.dumps(config))
    monkeypatch.setenv("COURIER_CONFIG_PATH", str(cfg))
    monkeypatch.setenv("COURIER_WORKER_STATE_DIR", str(tmp_path / "st"))
    monkeypatch.setenv("COURIER_WORKER_LOGS_DIR", str(tmp_path / "logs"))
    if key is None:
        monkeypatch.delenv("COURIER_API_KEY", raising=False)
    else:
        monkeypatch.setenv("COURIER_API_KEY", key)
    sys.path.insert(0, str(SCRIPTS))
    import daemon

    daemon = importlib.reload(daemon)

    def fake_security(command, **kwargs):
        service = command[command.index("-s") + 1] if "-s" in command else ""
        if service == "courier_api_key" and keychain_key is not None:
            return keychain_key.encode("utf-8")
        if service == "courier_server_url":
            return b"http://127.0.0.1:9/"
        raise subprocess.CalledProcessError(44, command)

    monkeypatch.setattr(daemon.subprocess, "check_output", fake_security)
    return daemon


def test_worker_log_redacts_api_key(monkeypatch, tmp_path):
    daemon = load_daemon(monkeypatch, tmp_path)
    daemon.load_config()
    daemon.write_log(f"registering with {FAKE_KEY} done")
    content = (tmp_path / "logs" / "worker.log").read_text()
    assert FAKE_KEY not in content
    assert "[REDACTED]" in content


def test_missing_api_key_fails_closed(monkeypatch, tmp_path):
    daemon = load_daemon(monkeypatch, tmp_path, key=None)
    with pytest.raises(SystemExit):
        daemon.load_config()


def test_worker_loads_api_key_from_keychain(monkeypatch, tmp_path):
    daemon = load_daemon(monkeypatch, tmp_path, key=None, keychain_key=FAKE_KEY)

    config = daemon.load_config()

    assert config["COURIER_API_KEY"] == FAKE_KEY


def test_repository_config_cannot_supply_api_key(monkeypatch, tmp_path):
    daemon = load_daemon(
        monkeypatch,
        tmp_path,
        key=None,
        keychain_key=None,
        config_key="TRACKED-PLAINTEXT-KEY",
    )

    with pytest.raises(SystemExit):
        daemon.load_config()


def test_tracked_mac_worker_config_contains_no_secret():
    config = json.loads(TRACKED_CONFIG.read_text())

    assert "COURIER_API_KEY" not in config


def test_keychain_setup_reads_secret_without_terminal_echo():
    script = KEYCHAIN_SETUP.read_text()

    assert 'read -r -s -p "Enter Courier API Key: " api_key' in script
    assert "unset api_key" in script
    assert "delete-generic-password" not in script
    commands = [line for line in script.splitlines() if "add-generic-password" in line]
    assert len(commands) == 2
    assert all(line.endswith(" -U") for line in commands)
