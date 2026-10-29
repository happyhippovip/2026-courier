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
@patch("scripts.render_godot_movie.sys.argv", new_callable=list)
def test_main_dry_run(mock_argv, mock_run, tmp_path):
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


# --- real (non dry-run) path: admission lock + verification ----------------

import json as _json
import subprocess as _subprocess

from scripts.render_godot_movie import heavy_job_lock, EXIT_ADMISSION_DENIED


def _project(tmp_path):
    for name in ("godot", "ffmpeg", "ffprobe"):
        (tmp_path / name).write_text("")
    (tmp_path / "main.tscn").write_text('[ext_resource path="res://script.gd" type="Script"]', encoding="utf-8")
    (tmp_path / "script.gd").write_text("const DURATION := 2.0\nconst CAPTURE_FPS := 30", encoding="utf-8")
    return [
        "render.py", "--project", str(tmp_path), "--scene", "res://main.tscn",
        "--output-dir", str(tmp_path / "out"), "--godot", str(tmp_path / "godot"),
        "--ffmpeg", str(tmp_path / "ffmpeg"), "--ffprobe", str(tmp_path / "ffprobe"),
        "--lock-file", str(tmp_path / "locks" / "heavy.lock"),
    ]


def _fake_run(width=360, height=640, duration="2.0", godot_rc=0):
    def run(cmd, **kwargs):
        if "--write-movie" in cmd:
            if godot_rc == 0:
                Path(cmd[cmd.index("--write-movie") + 1]).write_bytes(b"avi")
            return _subprocess.CompletedProcess(cmd, godot_rc, "", "")
        if "-show_entries" in cmd:
            out = _json.dumps({"streams": [{"codec_type": "video", "codec_name": "h264", "width": width, "height": height},
                                           {"codec_type": "audio", "codec_name": "aac"}],
                               "format": {"duration": duration}})
            return _subprocess.CompletedProcess(cmd, 0, out, "")
        Path(cmd[-1]).write_bytes(b"mp4")
        return _subprocess.CompletedProcess(cmd, 0, "", "")
    return run


def test_main_real_run_completes_and_verifies(tmp_path):
    args = _project(tmp_path)
    with patch("scripts.render_godot_movie.sys.argv", args), \
         patch("scripts.render_godot_movie.subprocess.run", side_effect=_fake_run()):
        assert main() == 0
    out = tmp_path / "out"
    assert (out / "render.mp4").is_file()
    assert not (out / "render.avi").exists()
    meta = _json.loads((out / "render_metadata.json").read_text())
    assert meta["frame_limit"] == 60 and meta["mp4_probe"]["width"] == 360


def test_main_denied_when_heavy_lock_held(tmp_path):
    args = _project(tmp_path)
    run = MagicMock()
    with heavy_job_lock(tmp_path / "locks" / "heavy.lock") as held:
        assert held
        with patch("scripts.render_godot_movie.sys.argv", args), \
             patch("scripts.render_godot_movie.subprocess.run", run):
            assert main() == EXIT_ADMISSION_DENIED
    run.assert_not_called()
    assert not (tmp_path / "out").exists()


def test_lock_is_released_after_run(tmp_path):
    args = _project(tmp_path)
    with patch("scripts.render_godot_movie.sys.argv", args), \
         patch("scripts.render_godot_movie.subprocess.run", side_effect=_fake_run()):
        assert main() == 0
    with heavy_job_lock(tmp_path / "locks" / "heavy.lock") as held:
        assert held


def test_godot_failure_preserves_state_and_fails(tmp_path):
    args = _project(tmp_path)
    with patch("scripts.render_godot_movie.sys.argv", args), \
         patch("scripts.render_godot_movie.subprocess.run", side_effect=_fake_run(godot_rc=1)):
        assert main() == 1
    assert not (tmp_path / "out" / "render.mp4").exists()


def test_wrong_resolution_is_rejected_and_avi_kept(tmp_path):
    args = _project(tmp_path)
    with patch("scripts.render_godot_movie.sys.argv", args), \
         patch("scripts.render_godot_movie.subprocess.run", side_effect=_fake_run(width=1080, height=1920)):
        assert main() == 1
    assert (tmp_path / "out" / "render.avi").is_file()
    assert not (tmp_path / "out" / "render_metadata.json").exists()


def test_custom_resolution_accepted(tmp_path):
    args = _project(tmp_path) + ["--width", "1080", "--height", "1920"]
    with patch("scripts.render_godot_movie.sys.argv", args), \
         patch("scripts.render_godot_movie.subprocess.run", side_effect=_fake_run(width=1080, height=1920)):
        assert main() == 0


def test_duration_mismatch_rejected(tmp_path):
    args = _project(tmp_path)
    with patch("scripts.render_godot_movie.sys.argv", args), \
         patch("scripts.render_godot_movie.subprocess.run", side_effect=_fake_run(duration="1.0")):
        assert main() == 1
