import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.render_godot_movie import (
    _required_constant,
    scene_script,
    movie_command,
    main
)

def test_required_constant(tmp_path):
    script = tmp_path / "test.gd"
    script.write_text("const DURATION := 12.5\nconst CAPTURE_FPS := 60", encoding="utf-8")
    assert _required_constant(script, "DURATION") == 12.5
    assert _required_constant(script, "CAPTURE_FPS") == 60.0

def test_required_constant_missing(tmp_path):
    script = tmp_path / "test.gd"
    script.write_text("const SOMETHING := 1.0", encoding="utf-8")
    with pytest.raises(ValueError, match="Required constant DURATION is missing"):
        _required_constant(script, "DURATION")

def test_scene_script(tmp_path):
    scene = tmp_path / "main.tscn"
    scene.write_text('[node name="Node2D" type="Node2D"]\n[ext_resource path="res://script.gd" type="Script"]\n', encoding="utf-8")
    
    script = tmp_path / "script.gd"
    script.write_text("extends Node2D", encoding="utf-8")

    res = scene_script(tmp_path, "res://main.tscn")
    assert res == script

def test_scene_script_invalid_prefix(tmp_path):
    with pytest.raises(ValueError, match="Scene must use a res:// path"):
        scene_script(tmp_path, "main.tscn")

def test_scene_script_no_script(tmp_path):
    scene = tmp_path / "main.tscn"
    scene.write_text('[node name="Node2D" type="Node2D"]', encoding="utf-8")
    with pytest.raises(ValueError, match="No attached GDScript found"):
        scene_script(tmp_path, "res://main.tscn")

def test_scene_script_missing_script(tmp_path):
    scene = tmp_path / "main.tscn"
    scene.write_text('[ext_resource path="res://missing.gd" type="Script"]', encoding="utf-8")
    with pytest.raises(ValueError, match="Attached GDScript does not exist"):
        scene_script(tmp_path, "res://main.tscn")

def test_movie_command():
    cmd = movie_command("godot.exe", Path("/proj"), "res://scene.tscn", Path("/out.avi"), 60, 300)
    assert cmd == [
        "godot.exe",
        "--rendering-driver", "opengl3",
        "--rendering-method", "gl_compatibility",
        "--path", str(Path("/proj")),
        "--write-movie", str(Path("/out.avi")),
        "--fixed-fps", "60",
        "--quit-after", "300",
        "-d",
        "res://scene.tscn",
    ]

@patch("scripts.render_godot_movie.subprocess.run")
def test_main_dry_run(mock_run, tmp_path):
    godot_exe = tmp_path / "godot.exe"
    godot_exe.write_text("")
    ffmpeg_exe = tmp_path / "ffmpeg.exe"
    ffmpeg_exe.write_text("")
    
    scene = tmp_path / "main.tscn"
    scene.write_text('[ext_resource path="res://script.gd" type="Script"]', encoding="utf-8")
    script = tmp_path / "script.gd"
    script.write_text("const DURATION := 2.0\nconst CAPTURE_FPS := 30", encoding="utf-8")
    
    out_dir = tmp_path / "out"
    
    test_args = [
        "render.py",
        "--project", str(tmp_path),
        "--scene", "res://main.tscn",
        "--output-dir", str(out_dir),
        "--godot", str(godot_exe),
        "--ffmpeg", str(ffmpeg_exe),
        "--dry-run"
    ]
    
    with patch("scripts.render_godot_movie.sys.argv", test_args):
        res = main()
        
    assert res == 0
    mock_run.assert_not_called()
