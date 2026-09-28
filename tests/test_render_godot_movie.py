import pytest
from pathlib import Path
import subprocess

def test_scene_script_parsing(tmp_path, monkeypatch):
    import scripts.render_godot_movie as script
    
    project = tmp_path / "project"
    project.mkdir()
    
    scene = project / "test.tscn"
    scene.write_text('path="res://test.gd"')
    
    gdscript = project / "test.gd"
    gdscript.write_text('const DURATION := 2.5\nconst CAPTURE_FPS := 60.0')
    
    parsed_script = script.scene_script(project, "res://test.tscn")
    assert parsed_script == gdscript
    
    duration = script._required_constant(parsed_script, "DURATION")
    fps = script._required_constant(parsed_script, "CAPTURE_FPS")
    
    assert duration == 2.5
    assert fps == 60.0

def test_movie_command():
    import scripts.render_godot_movie as script
    
    cmd = script.movie_command("godot", Path("/tmp/proj"), "res://test.tscn", Path("/tmp/out.avi"), 60, 150)
    assert "--write-movie" in cmd
    assert str(Path("/tmp/out.avi")) in cmd
    assert "--quit-after" in cmd
    assert "150" in cmd

