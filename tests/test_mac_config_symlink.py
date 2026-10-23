"""Mac worker config and state must not follow a symlink."""

import pytest

from scripts.mac_worker import daemon


def test_load_config_does_not_follow_a_symlink(tmp_path, monkeypatch):
    outside = tmp_path / "foreign.json"
    outside.write_text(
        '{"COURIER_API_KEY": "foreign-key", "COURIER_SERVER": "http://evil.invalid", "WORKER_ID": "mac"}\n',
        encoding="utf-8",
    )
    link = tmp_path / "config.json"
    link.symlink_to(outside)
    monkeypatch.setattr(daemon, "CONFIG_PATH", link)
    loaded = None
    try:
        loaded = daemon.load_config()
    except OSError as exc:
        assert "symlink" in str(exc)
    assert loaded is None
    assert "foreign-key" in outside.read_text(encoding="utf-8")


def test_worker_lock_does_not_follow_a_home_symlink(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir()
    home = tmp_path / "home"
    home.symlink_to(target, target_is_directory=True)
    monkeypatch.setattr(daemon, "STATE_DIR", home / "state")
    monkeypatch.setattr(daemon, "LOGS_DIR", home / "logs")
    try:
        daemon.acquire_worker_lock()
    except OSError as exc:
        assert "symlink" in str(exc)
    assert list(target.iterdir()) == []
