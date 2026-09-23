"""Secret hygiene for the Mac worker daemon: keys must never reach logs."""

import importlib
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "scripts" / "mac_worker"
FAKE_KEY = "TEST-FAKE-KEY-0123456789abcdef"


def load_daemon(monkeypatch, tmp_path, key=FAKE_KEY):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"WORKER_ID": "t", "COURIER_SERVER": "http://127.0.0.1:9/"}))
    monkeypatch.setenv("COURIER_CONFIG_PATH", str(cfg))
    monkeypatch.setenv("COURIER_WORKER_STATE_DIR", str(tmp_path / "st"))
    monkeypatch.setenv("COURIER_WORKER_LOGS_DIR", str(tmp_path / "logs"))
    if key is None:
        monkeypatch.delenv("COURIER_API_KEY", raising=False)
    else:
        monkeypatch.setenv("COURIER_API_KEY", key)
    sys.path.insert(0, str(SCRIPTS))
    import daemon

    return importlib.reload(daemon)


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


def test_worker_http_post_does_not_leak_key(monkeypatch, tmp_path, capsys):
    daemon = load_daemon(monkeypatch, tmp_path)
    cfg = daemon.load_config()
    daemon.http_post(cfg, "/dummy", {"test": 1})
    captured = capsys.readouterr()
    assert FAKE_KEY not in captured.out
    assert FAKE_KEY not in captured.err

