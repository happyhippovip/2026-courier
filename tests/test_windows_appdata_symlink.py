"""Windows daemon app data must not be created through a symlink."""

import importlib.util

import pytest

from tests.test_windows_worker_contract import DAEMON_PATH


def _load(monkeypatch):
    spec = importlib.util.spec_from_file_location("windows_worker_daemon_appdata_symlink", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(daemon)
    except OSError as exc:
        assert "symlink" in str(exc)
        return None
    return daemon


def test_localappdata_symlink_is_not_used(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "localappdata"
    link.symlink_to(target, target_is_directory=True)
    monkeypatch.setenv("LOCALAPPDATA", str(link))
    monkeypatch.delenv("COURIER_HOME", raising=False)
    loaded = _load(monkeypatch)
    assert list(target.iterdir()) == []
    assert loaded is None


def test_courier_dir_symlink_is_not_used(tmp_path, monkeypatch):
    local = tmp_path / "local"
    local.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    (local / "Courier").symlink_to(target, target_is_directory=True)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.delenv("COURIER_HOME", raising=False)
    loaded = _load(monkeypatch)
    assert list(target.iterdir()) == []
    assert loaded is None


def test_log_dir_symlink_is_not_used(tmp_path, monkeypatch):
    local = tmp_path / "local"
    (local / "Courier").mkdir(parents=True)
    target = tmp_path / "target"
    target.mkdir()
    (local / "Courier" / "logs").symlink_to(target, target_is_directory=True)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.delenv("COURIER_HOME", raising=False)
    loaded = _load(monkeypatch)
    assert list(target.iterdir()) == []
    assert loaded is None


def test_courier_home_symlink_is_not_used(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "home"
    link.symlink_to(target, target_is_directory=True)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("COURIER_HOME", str(link))
    loaded = _load(monkeypatch)
    assert list(target.iterdir()) == []
    assert loaded is None
