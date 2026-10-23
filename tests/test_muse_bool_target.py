"""A bool is not a Muse slot count. True must not enable slot 01."""

import json

import pytest

pytest.importorskip("fcntl")

import scripts.mac_worker.muse_supervisor as supervisor


def _redirect(monkeypatch, tmp_path):
    monkeypatch.setattr(supervisor, "WALL_DIR", tmp_path)
    monkeypatch.setattr(supervisor, "SLOTS_FILE", tmp_path / "slots.json")
    monkeypatch.setattr(supervisor, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(supervisor, "STOP_FILE", tmp_path / "STOP")
    monkeypatch.setattr(supervisor, "LOCK_FILE", tmp_path / "supervisor.lock")


def test_bool_build_does_not_create_one_slot(tmp_path, monkeypatch):
    _redirect(monkeypatch, tmp_path)
    code = supervisor.cmd_build(True)
    names = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert code == 2, (code, names)
    assert names == []


def test_bool_start_does_not_enable_one_slot(tmp_path, monkeypatch):
    _redirect(monkeypatch, tmp_path)
    code = supervisor.cmd_start(True, loop=False)
    names = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert code == 2, (code, names)
    assert names == []


def test_bool_config_target_is_not_one_slot(tmp_path, monkeypatch):
    _redirect(monkeypatch, tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({"target": True}), encoding="utf-8")
    try:
        sup = supervisor.Supervisor(clock=lambda: 0)
    except ValueError as exc:
        assert "bool" in str(exc).lower(), exc
    else:
        raise AssertionError(sup.gov.requested_max)
    with pytest.raises(ValueError):
        supervisor.Supervisor(clock=lambda: 0)
    (tmp_path / "config.json").write_text(json.dumps({"target": False}), encoding="utf-8")
    with pytest.raises(ValueError):
        supervisor.Supervisor(clock=lambda: 0)
