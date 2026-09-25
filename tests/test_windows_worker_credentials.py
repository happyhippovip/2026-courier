import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "windows_worker" / "daemon.py"
DUMMY_KEY = "dummy-test-key-not-real"


def load(monkeypatch, key=None, url=None):
    if key is None:
        monkeypatch.delenv("COURIER_API_KEY", raising=False)
    else:
        monkeypatch.setenv("COURIER_API_KEY", key)
    if url is None:
        monkeypatch.delenv("COURIER_SERVER_URL", raising=False)
    else:
        monkeypatch.setenv("COURIER_SERVER_URL", url)
    spec = importlib.util.spec_from_file_location("windows_daemon_creds", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    return daemon


def test_no_hardcoded_key_in_source():
    src = DAEMON_PATH.read_text()
    assert "prod-secret" not in src
    assert 'API_KEY = "' not in src


def test_key_and_url_come_from_environment(monkeypatch):
    d = load(monkeypatch, key=DUMMY_KEY, url="http://example.invalid:9/")
    assert d.API_KEY == DUMMY_KEY
    assert d.API_URL == "http://example.invalid:9"
    assert d.HEADERS["Authorization"] == f"Bearer {DUMMY_KEY}"


@pytest.mark.parametrize("key", [None, "", "   "])
def test_missing_key_fails_closed_without_network(monkeypatch, key):
    d = load(monkeypatch, key=key)
    calls = []
    monkeypatch.setattr(d.urllib.request, "urlopen", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(d, "load_config", lambda: calls.append("config") or {"WORKER_ID": "W"})
    with pytest.raises(d.MissingCredentialError):
        d.loop()
    with pytest.raises(d.MissingCredentialError):
        d.register_worker("W")
    with pytest.raises(d.MissingCredentialError):
        d.http_post_result({"task_id": "t"})
    assert calls == []


def test_main_exits_nonzero_and_never_prints_key(tmp_path):
    env = {"PATH": "/usr/bin:/bin", "COURIER_SERVER_URL": "http://127.0.0.1:9"}
    r = subprocess.run([sys.executable, str(DAEMON_PATH)], env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 2
    assert "COURIER_API_KEY" in r.stderr
    assert "Bearer" not in r.stdout + r.stderr


def test_register_failure_does_not_leak_key(monkeypatch, capsys):
    d = load(monkeypatch, key=DUMMY_KEY)

    def boom(req, *a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(d.urllib.request, "urlopen", boom)
    assert d.register_worker("W") is False
    out = capsys.readouterr()
    assert DUMMY_KEY not in out.out + out.err
    assert "Authorization" not in out.out + out.err
