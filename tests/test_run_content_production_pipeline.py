import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scripts.run_content_production_pipeline import (
    load_json,
    save_json,
    sha256_file,
    slugify,
    check_secrets_in_text,
    discover_godot_binary,
    execute_idea_stage,
    execute_hook_stage,
    execute_script_stage,
    execute_assets_stage,
    execute_video_build_stage,
    execute_metadata_stage,
    execute_review_stage,
    execute_ready_to_publish_stage,
    run_pipeline,
    main
)

def test_load_save_json(tmp_path):
    f = tmp_path / "test.json"
    save_json(f, {"a": 1})
    assert load_json(f) == {"a": 1}

def test_sha256_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello", encoding="utf-8")
    assert sha256_file(f) == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

def test_slugify():
    assert slugify("Hello World! 123") == "hello-world-123"

def test_check_secrets_in_text():
    assert check_secrets_in_text("hello world") == 0
    assert check_secrets_in_text("my password='SuperSecret123'") == 1
    assert check_secrets_in_text("ghp_12345678901234567890") == 1
    assert check_secrets_in_text("sk-12345678901234567890") == 1
    assert check_secrets_in_text("AIza12345678901234567890123456789012345") == 1
    assert check_secrets_in_text("-----BEGIN RSA PRIVATE KEY-----\nasd\n-----END PRIVATE KEY-----") == 1

def test_discover_godot_binary_custom_path_success(monkeypatch):
    def mock_run(*args, **kwargs):
        return MagicMock(returncode=0, stdout="4.7.stable")
    monkeypatch.setattr("subprocess.run", mock_run)
    monkeypatch.setattr("os.path.exists", lambda x: True)
    
    bin_path, version = discover_godot_binary("my_godot")
    assert bin_path == "my_godot"
    assert version == "4.7.stable"

def test_discover_godot_binary_custom_path_exception(monkeypatch):
    def mock_run(*args, **kwargs):
        raise Exception("error")
    monkeypatch.setattr("subprocess.run", mock_run)
    monkeypatch.setattr("os.path.exists", lambda x: True)
    
    bin_path, version = discover_godot_binary("my_godot")
    assert bin_path == "my_godot"
    assert version == "4.7.stable.official.5b4e0cb0f"

def test_discover_godot_binary_which(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda x: "godot_from_path")
    monkeypatch.setattr("os.path.exists", lambda x: False)
    def mock_run(*args, **kwargs):
        return MagicMock(returncode=0, stdout="4.7.stable")
    monkeypatch.setattr("subprocess.run", mock_run)
    
    bin_path, version = discover_godot_binary()
    assert bin_path == "godot_from_path"
    assert version == "4.7.stable"

def test_discover_godot_binary_which_exception(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda x: "godot_from_path")
    monkeypatch.setattr("os.path.exists", lambda x: False)
    def mock_run(*args, **kwargs):
        raise Exception("error")
    monkeypatch.setattr("subprocess.run", mock_run)
    
    bin_path, version = discover_godot_binary()
    assert bin_path is None
    assert version is None

def test_execute_idea_stage(tmp_path):
    f = execute_idea_stage(tmp_path, "my-topic", "FruitKI", "YOUTUBE")
    assert f.exists()
    data = load_json(f)
    assert data["topic"] == "my-topic"

def test_execute_hook_stage(tmp_path):
    f = execute_hook_stage(tmp_path, "my-topic")
    assert f.exists()
    data = load_json(f)
    assert data["topic"] == "my-topic"

def test_execute_script_stage(tmp_path):
    f = execute_script_stage(tmp_path, "my-topic", "FruitKI")
    assert f.exists()
    assert (tmp_path / "script.json").exists()

def test_execute_assets_stage(tmp_path):
    f = execute_assets_stage(tmp_path, "my-topic", "FruitKI", {})
    assert f.exists()

def test_execute_video_build_stage_ffmpeg_success(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda x: "ffmpeg")
    monkeypatch.setattr("os.path.exists", lambda x: True)
    
    def mock_run(cmd, *args, **kwargs):
        if cmd[0] == "ffmpeg":
            (tmp_path / "my-topic_preview.mp4").write_bytes(b"data")
        return MagicMock(returncode=0, stdout="4.7.stable")
    monkeypatch.setattr("subprocess.run", mock_run)
    
    status, f, details = execute_video_build_stage(tmp_path, "my-topic", "FruitKI", {})
    assert status == "COMPLETED"
    assert f is not None
    assert details["ffmpeg_preview_render"]["status"] == "COMPLETED"
    assert details["godot_real_3d_render"]["status"] == "ENVIRONMENT_GATE"

def test_execute_video_build_stage_ffmpeg_fail(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda x: "ffmpeg")
    original_exists = os.path.exists
    def custom_exists(x):
        if "ffmpeg" in str(x):
            return True
        return original_exists(x)
    monkeypatch.setattr("os.path.exists", custom_exists)
    
    def mock_run(cmd, *args, **kwargs):
        raise Exception("fail")
    monkeypatch.setattr("subprocess.run", mock_run)
    
    status, f, details = execute_video_build_stage(tmp_path, "my-topic", "FruitKI", {})
    assert status == "ENVIRONMENT_GATE"
    assert f is None
    assert details["ffmpeg_preview_render"]["status"] == "FAILED"

def test_execute_video_build_stage_godot_success(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda x: None)
    
    # Mock os.path.exists to true for both custom path and project bound
    original_exists = os.path.exists
    def custom_exists(p):
        if "my_godot" in str(p) or "my_project" in str(p):
            return True
        return original_exists(p)
    monkeypatch.setattr("os.path.exists", custom_exists)
    
    def mock_run(*args, **kwargs):
        return MagicMock(returncode=0, stdout="4.7.stable")
    monkeypatch.setattr("subprocess.run", mock_run)
    
    local_tools = {
        "tools": {"godot_binary_path": "my_godot"},
        "project_bindings": {"FruitKI": {"project_path": "my_project"}}
    }
    
    status, f, details = execute_video_build_stage(tmp_path, "my-topic", "FruitKI", local_tools)
    assert status == "COMPLETED"
    assert details["godot_real_3d_render"]["status"] == "BOUND_AND_VERIFIED"

def test_execute_metadata_stage(tmp_path):
    f_yt = execute_metadata_stage(tmp_path, "my-topic", "FruitKI", "YOUTUBE")
    assert f_yt.exists()
    assert load_json(f_yt)["platform"] == "YOUTUBE"
    
    f_tt = execute_metadata_stage(tmp_path, "my-topic", "FruitKI", "TIKTOK")
    assert f_tt.exists()
    assert load_json(f_tt)["platform"] == "TIKTOK"

def test_execute_review_stage(tmp_path):
    art1 = tmp_path / "a1.json"
    save_json(art1, {"a": 1})
    art2 = tmp_path / "a2.txt"
    art2.write_text("secret='SuperSecret12345'", encoding="utf-8")
    
    artifacts = [
        {"artifact_name": "a1.json", "absolute_path": str(art1)},
        {"artifact_name": "a2.txt", "absolute_path": str(art2)},
        {"artifact_name": "a3.txt", "absolute_path": str(tmp_path / "missing.txt")},
    ]
    
    res, f = execute_review_stage(tmp_path, artifacts)
    assert res["verdict"] == "FAIL"
    assert res["secrets_detected"] == 1
    assert len(res["missing_artifacts"]) == 1

def test_execute_ready_to_publish_stage(tmp_path):
    meta = tmp_path / "meta.json"
    save_json(meta, {"platform": "YOUTUBE"})
    
    res, f = execute_ready_to_publish_stage(tmp_path, {"verdict": "PASS"}, meta, [{"relative_path": "a1.json"}])
    assert res["package_ready"] is True
    assert res["status"] == "STAGED_AWAITING_HUMAN_CONSENT"
    
    res_fail, _ = execute_ready_to_publish_stage(tmp_path, {"verdict": "FAIL"}, None, [])
    assert res_fail["package_ready"] is False

def test_run_pipeline_success(tmp_path, monkeypatch):
    channels = tmp_path / "channels.json"
    save_json(channels, {
        "channels": [
            {"channel_id": "c1", "workflow_id": "w1", "platform": "YOUTUBE", "content_project": "FruitKI"}
        ]
    })
    
    workflows = tmp_path / "workflows.json"
    save_json(workflows, {
        "workflows": [
            {"workflow_id": "w1", "production_steps": ["IDEA", "HOOK", "SCRIPT", "ASSET_SELECTION", "VIDEO_BUILD", "METADATA", "REVIEW", "READY_TO_PUBLISH"]}
        ]
    })
    
    local_tools = tmp_path / "local_tools.json"
    save_json(local_tools, {})
    
    runtime = tmp_path / "runtime"
    
    monkeypatch.setattr("scripts.run_content_production_pipeline.execute_video_build_stage", lambda *args: ("COMPLETED", None, {}))
    monkeypatch.setattr("scripts.run_content_production_pipeline.execute_review_stage", lambda *args: ({"verdict": "PASS"}, args[0] / "review.json"))
    monkeypatch.setattr("scripts.run_content_production_pipeline.execute_ready_to_publish_stage", lambda *args: ({"package_ready": True, "status": "STAGED_AWAITING_HUMAN_CONSENT"}, args[0] / "publish.json"))

    manifest = run_pipeline(
        "c1",
        "topic1",
        "mission1",
        runtime,
        channels,
        workflows,
        local_tools
    )
    
    assert manifest["overall_status"] == "COMPLETED"
    
    # Test dedupe
    manifest2 = run_pipeline(
        "c1",
        "topic1",
        "mission1",
        runtime,
        channels,
        workflows,
        local_tools
    )
    assert manifest2["overall_status"] == "COMPLETED"

def test_run_pipeline_missing_config(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_pipeline("c1", channels_path=tmp_path / "nonexistent.json")

    c = tmp_path / "c.json"
    save_json(c, {})
    with pytest.raises(FileNotFoundError):
        run_pipeline("c1", channels_path=c, workflows_path=tmp_path / "nonexistent2.json")

def test_run_pipeline_missing_channel(tmp_path):
    c = tmp_path / "c.json"
    save_json(c, {})
    w = tmp_path / "w.json"
    save_json(w, {})
    with pytest.raises(ValueError, match="Channel 'c1' not found"):
        run_pipeline("c1", channels_path=c, workflows_path=w)

def test_run_pipeline_missing_workflow(tmp_path):
    c = tmp_path / "c.json"
    save_json(c, {"channels": [{"channel_id": "c1", "workflow_id": "w1"}]})
    w = tmp_path / "w.json"
    save_json(w, {})
    with pytest.raises(ValueError, match="Workflow 'w1' not found"):
        run_pipeline("c1", channels_path=c, workflows_path=w)

def test_main(monkeypatch):
    monkeypatch.setattr("sys.argv", [
        "run_content_production_pipeline.py",
        "--channel-id", "c1",
        "--topic", "t1",
        "--mission-id", "m1",
        "--runtime-dir", "r1",
        "--config", "c1.json",
        "--workflows-config", "w1.json",
        "--tools-config", "t1.json",
        "--force"
    ])
    
    with patch("scripts.run_content_production_pipeline.run_pipeline") as mock_run:
        mock_run.return_value = {"status": "ok"}
        with patch("builtins.print") as mock_print:
            main()
            mock_run.assert_called_once()
            mock_print.assert_called_with('{\n  "status": "ok"\n}')

def test_main_block(monkeypatch):
    import sys
    from pathlib import Path
    
    with patch("sys.argv", ["run_content_production_pipeline.py", "--channel-id", "c1", "--topic", "t1", "--mission-id", "m1"]):
        with patch("scripts.run_content_production_pipeline.run_pipeline") as mock_run:
            mock_run.return_value = {"status": "ok"}
            
            # just test main itself
            from scripts.run_content_production_pipeline import main
            main()
            mock_run.assert_called_once()
