"""The Muse supervisor lock must not follow a symlink."""

import pytest

pytest.importorskip("fcntl")

from scripts.mac_worker import muse_supervisor as sup


def test_wall_symlink_is_not_used_for_the_lock(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir()
    wall = tmp_path / "wall"
    wall.symlink_to(target, target_is_directory=True)
    monkeypatch.setattr(sup, "WALL_DIR", wall)
    monkeypatch.setattr(sup, "LOCK_FILE", wall / "supervisor.lock")
    try:
        sup.acquire_lock()
    except OSError as exc:
        assert "symlink" in str(exc)
    assert list(target.iterdir()) == []


def test_lock_file_symlink_is_not_truncated(tmp_path, monkeypatch):
    wall = tmp_path / "wall"
    wall.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")
    lock = wall / "supervisor.lock"
    lock.symlink_to(outside)
    monkeypatch.setattr(sup, "WALL_DIR", wall)
    monkeypatch.setattr(sup, "LOCK_FILE", lock)
    try:
        sup.acquire_lock()
    except OSError as exc:
        assert "symlink" in str(exc)
    assert outside.read_text(encoding="utf-8") == "keep"
