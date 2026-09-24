"""Unit tests for scripts/render_godot_movie.py."""
import json
import subprocess
import sys
from pathlib import Path
import pytest

from scripts.render_godot_movie import (
    _required_constant,
    movie_command,
    scene_script,
    main as render_movie_main,
)


def test_required_constant(tmp_path):
    gd_file = tmp_path / "test.gd"
    gd_file.write_text("extends Node\nconst DURATION := 7.125\nconst CAPTURE_FPS := 30\n", encoding="utf-8")
    assert _required_constant(gd_file, "DURATION") == 7.125
    assert _required_constant(gd_file, "CAPTURE_FPS") == 30.0

    with pytest.raises(ValueError):
        _required_constant(gd_file, "NONEXISTENT")


def test_movie_command():
    godot_path = "/usr/bin/godot"
    project_dir = Path("/home/user/project")
    scene = "res://main.tscn"
    avi = Path("/home/user/output/render.avi")
    fps = 30
    frames = 214

    cmd = movie_command(godot_path, project_dir, scene, avi, fps, frames)
    assert cmd[0] == godot_path
    assert "--rendering-driver" in cmd
    assert "--write-movie" in cmd
    assert str(avi) in cmd
    assert "--fixed-fps" in cmd
    assert "30" in cmd
    assert "--quit-after" in cmd
    assert "214" in cmd
    assert scene in cmd


def test_render_godot_movie_dry_run_with_auto_discovery(tmp_path, capsys):
    cur = Path(__file__).resolve()
    project_dir = None
    while cur.parent != cur:
        if (cur / "2026-godot-shorts" / "project.godot").is_file():
            project_dir = cur / "2026-godot-shorts"
            break
        cur = cur.parent
    if not project_dir:
        project_dir = Path(r"C:\Users\lol\2026-workspace\2026-godot-shorts")
    scene = "res://strawberry_school_short.tscn"
    output_dir = tmp_path / "render_out"

    ret = render_movie_main([
        "--project", str(project_dir),
        "--scene", scene,
        "--output-dir", str(output_dir),
        "--dry-run"
    ])

    assert ret == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip())
    assert payload["duration_seconds"] == 7.0
    assert payload["fps"] == 24
    assert payload["frame_limit"] == 168
    assert "--write-movie" in payload["command"]
    assert "--fixed-fps" in payload["command"]
    assert "--quit-after" in payload["command"]
    assert "168" in payload["command"]
