import os
import sys
import json
import zipfile
from unittest import mock
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import support_bundle

def test_get_system_health():
    health = support_bundle.get_system_health()
    assert "os" in health
    assert "disk_free_gb" in health

def test_create_support_bundle(tmp_path, capsys):
    # Change working dir to tmp_path so the zip is created there
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        # Create a mock central_state.json
        state_file = tmp_path / "central_state.json"
        state_file.write_text(json.dumps({
            "goals": {"g1": {}, "g2": {}},
            "tasks": {"t1": {}, "t2": {}, "t3": {}},
            "secret_key": "DO_NOT_INCLUDE"
        }))
        
        with mock.patch("subprocess.check_output", return_value=b"abcdef123456\n"):
            support_bundle.create_support_bundle()
            
        # Find the created zip
        zips = list(tmp_path.glob("support_bundle_*.zip"))
        assert len(zips) == 1
        zip_path = zips[0]
        
        # Read zip contents
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "health.json" in files
            assert "queue_summary.json" in files
            assert "version.txt" in files
            
            queue_summary = json.loads(zf.read("queue_summary.json"))
            assert queue_summary["queue_summary"]["total_goals"] == 2
            assert queue_summary["queue_summary"]["total_tasks"] == 3
            assert "secret_key" not in queue_summary
            
            version = zf.read("version.txt").decode()
            assert "git_hash: abcdef123456" in version
            
    finally:
        os.chdir(original_cwd)

def test_create_support_bundle_no_git(tmp_path):
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        with mock.patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "git")):
            support_bundle.create_support_bundle()
            
        zips = list(tmp_path.glob("support_bundle_*.zip"))
        assert len(zips) == 1
        
        with zipfile.ZipFile(zips[0], 'r') as zf:
            version = zf.read("version.txt").decode()
            assert "version: unknown" in version
            
    finally:
        os.chdir(original_cwd)
        
