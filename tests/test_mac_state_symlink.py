"""Mac worker state must not follow a symlink into another directory."""

import pytest

pytest.importorskip("fcntl")

from scripts.mac_worker.runtime_state import atomic_json, control_lock, read_object


def test_read_object_does_not_adopt_a_symlink(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text('{"state": "CLEAN"}', encoding="utf-8")
    link = tmp_path / "marker.json"
    link.symlink_to(outside)
    with pytest.raises(OSError, match="symlink"):
        read_object(link)
    assert outside.read_text(encoding="utf-8") == '{"state": "CLEAN"}'


def test_atomic_json_does_not_write_through_a_parent_symlink(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(OSError, match="symlink"):
        atomic_json(link / "state.json", {"state": "CLEAN"})
    assert not (target / "state.json").exists()
    assert list(target.iterdir()) == []


def test_control_lock_does_not_follow_a_wall_symlink(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    wall = tmp_path / "wall"
    wall.symlink_to(target, target_is_directory=True)
    with pytest.raises(OSError, match="symlink"):
        with control_lock(wall):
            pass
    assert not (target / "control.lock").exists()
