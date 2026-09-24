import json
from pathlib import Path
import pytest
from scripts.render_godot_movie import _required_constant, scene_script, movie_command, main


def test_required_constant_and_scene_script(tmp_path: Path):
    proj_dir = tmp_path / "project"
    proj_dir.mkdir()

    gd_file = proj_dir / "main.gd"
    gd_file.write_text(
        "extends Node2D\n\nconst DURATION := 12.5\nconst CAPTURE_FPS := 60\n",
        encoding="utf-8",
    )

    tscn_file = proj_dir / "main.tscn"
    tscn_file.write_text(
        '[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://main.gd" id="1_abc"]\n',
        encoding="utf-8",
    )

    assert _required_constant(gd_file, "DURATION") == 12.5
    assert _required_constant(gd_file, "CAPTURE_FPS") == 60.0

    script_path = scene_script(proj_dir, "res://main.tscn")
    assert script_path == gd_file


def test_movie_command():
    cmd = movie_command(
        godot="godot.exe",
        project=Path("C:/proj"),
        scene="res://main.tscn",
        avi=Path("C:/proj/out/render.avi"),
        fps=30,
        frames=300,
    )
    assert cmd[0] == "godot.exe"
    assert "--quit-after" in cmd
    assert "300" in cmd
    assert "res://main.tscn" in cmd


def test_render_godot_movie_dry_run(tmp_path: Path, capsys):
    proj_dir = tmp_path / "project"
    proj_dir.mkdir()

    gd_file = proj_dir / "main.gd"
    gd_file.write_text(
        "extends Node2D\n\nconst DURATION := 5.0\nconst CAPTURE_FPS := 30\n",
        encoding="utf-8",
    )

    tscn_file = proj_dir / "main.tscn"
    tscn_file.write_text(
        '[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://main.gd" id="1_abc"]\n',
        encoding="utf-8",
    )

    out_dir = tmp_path / "output"

    ret = main([
        "--project", str(proj_dir),
        "--scene", "res://main.tscn",
        "--output-dir", str(out_dir),
        "--dry-run",
    ])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["duration_seconds"] == 5.0
    assert data["fps"] == 30
    assert data["frame_limit"] == 150
