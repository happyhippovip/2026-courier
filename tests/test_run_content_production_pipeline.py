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

def test_ids_do_not_escape_the_runtime_dir(tmp_path):
    runtime = tmp_path / "repo" / "runtime" / "content"
    runtime.mkdir(parents=True)
    workflows = tmp_path / "workflows.json"
    save_json(workflows, {"workflows": [{"workflow_id": "w1", "production_steps": []}]})
    tools = tmp_path / "tools.json"
    channels = tmp_path / "channels.json"
    save_json(channels, {
        "channels": [{
            "channel_id": "../../../outside-channel",
            "workflow_id": "w1",
            "platform": "YOUTUBE",
            "content_project": "FruitKI",
        }]
    })
    try:
        run_pipeline(
            "../../../outside-channel",
            "topic",
            "mission-1",
            runtime,
            channels,
            workflows,
            tools,
        )
        err = None
    except ValueError as exc:
        err = str(exc)
    manifest = tmp_path / "outside-channel" / "mission-1" / "manifest.json"
    body = manifest.read_text(encoding="utf-8") if manifest.exists() else ""
    safe_channels = tmp_path / "safe-channels.json"
    save_json(safe_channels, {
        "channels": [{
            "channel_id": "c1",
            "workflow_id": "w1",
            "platform": "YOUTUBE",
            "content_project": "FruitKI",
        }]
    })
    try:
        run_pipeline(
            "c1",
            "topic",
            "../../../../outside-mission",
            runtime,
            safe_channels,
            workflows,
            tools,
        )
        err2 = None
    except ValueError as exc:
        err2 = str(exc)
    manifest2 = tmp_path / "outside-mission" / "manifest.json"
    body2 = manifest2.read_text(encoding="utf-8") if manifest2.exists() else ""
    assert (err, "outside-channel" in body, err2, "outside-mission" in body2) == (
        "refusing an unsafe channel id",
        False,
        "refusing an unsafe mission id",
        False,
    )

def test_runtime_dir_does_not_follow_a_symlink(tmp_path, monkeypatch):
    runtime_root = tmp_path / "repo" / "runtime"
    runtime_root.mkdir(parents=True)
    workflows = tmp_path / "workflows.json"
    save_json(workflows, {"workflows": [{"workflow_id": "w1", "production_steps": []}]})
    tools = tmp_path / "tools.json"
    channels = tmp_path / "channels.json"
    save_json(channels, {
        "channels": [{
            "channel_id": "c1",
            "workflow_id": "w1",
            "platform": "YOUTUBE",
            "content_project": "FruitKI",
        }]
    })
    outside = tmp_path / "outside-runtime"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    runtime = tmp_path / "runtime"
    runtime.symlink_to(outside)
    try:
        run_pipeline("c1", "topic", "mission-1", runtime, channels, workflows, tools)
        err = None
    except ValueError as exc:
        err = str(exc)
    manifest = outside / "c1" / "mission-1" / "manifest.json"
    body = manifest.read_text(encoding="utf-8") if manifest.exists() else ""
    parent_outside = tmp_path / "parent-outside"
    parent_outside.mkdir()
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(parent_outside)
    try:
        run_pipeline(
            "c1",
            "topic",
            "mission-2",
            linked_parent / "content",
            channels,
            workflows,
            tools,
        )
        err2 = None
    except ValueError as exc:
        err2 = str(exc)
    parent_manifest = parent_outside / "content" / "c1" / "mission-2" / "manifest.json"
    parent_body = parent_manifest.read_text(encoding="utf-8") if parent_manifest.exists() else ""
    names = sorted(path.name for path in parent_outside.iterdir())
    cli_outside = tmp_path / "cli-outside"
    cli_outside.mkdir()
    (cli_outside / "keep.txt").write_text("keep", encoding="utf-8")
    cli_link = tmp_path / "cli-runtime"
    cli_link.symlink_to(cli_outside)
    monkeypatch.setattr(sys, "argv", [
        "run_content_production_pipeline.py",
        "--channel-id", "c1",
        "--topic", "topic",
        "--mission-id", "mission-3",
        "--runtime-dir", str(cli_link),
        "--config", str(channels),
        "--workflows-config", str(workflows),
        "--tools-config", str(tools),
    ])
    try:
        main()
        err3 = None
    except ValueError as exc:
        err3 = str(exc)
    cli_manifest = cli_outside / "c1" / "mission-3" / "manifest.json"
    cli_body = cli_manifest.read_text(encoding="utf-8") if cli_manifest.exists() else ""
    assert (
        err,
        "mission-1" in body,
        err2,
        "mission-2" in parent_body,
        names,
        err3,
        "mission-3" in cli_body,
    ) == (
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        False,
        ["keep.txt"],
        "refusing to follow a symlink",
        False,
    )

def _channel_file(path: Path, project: str) -> None:
    save_json(path, {
        "channels": [{
            "channel_id": "c1",
            "workflow_id": "w1",
            "platform": "YOUTUBE",
            "content_project": project,
        }]
    })

def test_channels_config_does_not_follow_a_symlink(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    workflows = tmp_path / "workflows.json"
    save_json(workflows, {"workflows": [{"workflow_id": "w1", "production_steps": []}]})
    tools = tmp_path / "tools.json"
    outside = tmp_path / "outside-channels.json"
    _channel_file(outside, "SECRET-CHANNEL")
    channels = tmp_path / "channels.json"
    channels.symlink_to(outside)
    try:
        run_pipeline("c1", "topic", "mission-1", runtime, channels, workflows, tools)
        err = None
    except ValueError as exc:
        err = str(exc)
    body = (runtime / "c1" / "mission-1" / "manifest.json")
    text = body.read_text(encoding="utf-8") if body.exists() else ""
    parent_outside = tmp_path / "parent-outside"
    parent_outside.mkdir()
    _channel_file(parent_outside / "channels.json", "SECRET-PARENT")
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(parent_outside)
    try:
        run_pipeline(
            "c1",
            "topic",
            "mission-2",
            runtime,
            linked_parent / "channels.json",
            workflows,
            tools,
        )
        err2 = None
    except ValueError as exc:
        err2 = str(exc)
    body2 = runtime / "c1" / "mission-2" / "manifest.json"
    text2 = body2.read_text(encoding="utf-8") if body2.exists() else ""
    cli_outside = tmp_path / "cli-channels.json"
    _channel_file(cli_outside, "SECRET-CLI")
    cli_link = tmp_path / "cli-channels-link.json"
    cli_link.symlink_to(cli_outside)
    monkeypatch.setattr(sys, "argv", [
        "run_content_production_pipeline.py",
        "--channel-id", "c1",
        "--topic", "topic",
        "--mission-id", "mission-3",
        "--runtime-dir", str(runtime),
        "--config", str(cli_link),
        "--workflows-config", str(workflows),
        "--tools-config", str(tools),
    ])
    try:
        main()
        err3 = None
    except ValueError as exc:
        err3 = str(exc)
    body3 = runtime / "c1" / "mission-3" / "manifest.json"
    text3 = body3.read_text(encoding="utf-8") if body3.exists() else ""
    assert (
        err,
        "SECRET-CHANNEL" in text,
        err2,
        "SECRET-PARENT" in text2,
        err3,
        "SECRET-CLI" in text3,
    ) == (
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        False,
    )
    assert "SECRET-CHANNEL" in outside.read_text(encoding="utf-8")
    assert "SECRET-PARENT" in (parent_outside / "channels.json").read_text(encoding="utf-8")
    assert "SECRET-CLI" in cli_outside.read_text(encoding="utf-8")

def _workflow_file(path: Path, steps: list[str]) -> None:
    save_json(path, {"workflows": [{"workflow_id": "w1", "production_steps": steps}]})

def test_workflows_config_does_not_follow_a_symlink(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    channels = tmp_path / "channels.json"
    _channel_file(channels, "FruitKI")
    tools = tmp_path / "tools.json"
    outside = tmp_path / "outside-workflows.json"
    _workflow_file(outside, ["IDEA"])
    workflows = tmp_path / "workflows.json"
    workflows.symlink_to(outside)
    try:
        run_pipeline("c1", "topic", "mission-1", runtime, channels, workflows, tools)
        err = None
    except ValueError as exc:
        err = str(exc)
    body = runtime / "c1" / "mission-1" / "manifest.json"
    text = body.read_text(encoding="utf-8") if body.exists() else ""
    parent_outside = tmp_path / "parent-outside"
    parent_outside.mkdir()
    _workflow_file(parent_outside / "workflows.json", ["IDEA"])
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(parent_outside)
    try:
        run_pipeline(
            "c1",
            "topic",
            "mission-2",
            runtime,
            channels,
            linked_parent / "workflows.json",
            tools,
        )
        err2 = None
    except ValueError as exc:
        err2 = str(exc)
    body2 = runtime / "c1" / "mission-2" / "manifest.json"
    text2 = body2.read_text(encoding="utf-8") if body2.exists() else ""
    cli_outside = tmp_path / "cli-workflows.json"
    _workflow_file(cli_outside, ["IDEA"])
    cli_link = tmp_path / "cli-workflows-link.json"
    cli_link.symlink_to(cli_outside)
    monkeypatch.setattr(sys, "argv", [
        "run_content_production_pipeline.py",
        "--channel-id", "c1",
        "--topic", "topic",
        "--mission-id", "mission-3",
        "--runtime-dir", str(runtime),
        "--config", str(channels),
        "--workflows-config", str(cli_link),
        "--tools-config", str(tools),
    ])
    try:
        main()
        err3 = None
    except ValueError as exc:
        err3 = str(exc)
    body3 = runtime / "c1" / "mission-3" / "manifest.json"
    text3 = body3.read_text(encoding="utf-8") if body3.exists() else ""
    assert (err, "IDEA" in text, err2, "IDEA" in text2, err3, "IDEA" in text3) == (
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        False,
    )
    assert "IDEA" in outside.read_text(encoding="utf-8")

def _tools_file(path: Path, marker: str) -> None:
    save_json(path, {
        "project_bindings": {
            "FruitKI": {"project_path": marker, "default_scene": "Main.tscn"}
        }
    })

def test_tools_config_does_not_follow_a_symlink(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    channels = tmp_path / "channels.json"
    _channel_file(channels, "FruitKI")
    workflows = tmp_path / "workflows.json"
    _workflow_file(workflows, ["ASSET_SELECTION"])
    outside = tmp_path / "outside-tools.json"
    _tools_file(outside, "SECRET-TOOLS")
    tools = tmp_path / "tools.json"
    tools.symlink_to(outside)
    try:
        run_pipeline("c1", "topic", "mission-1", runtime, channels, workflows, tools)
        err = None
    except ValueError as exc:
        err = str(exc)
    assets = runtime / "c1" / "mission-1" / "asset-selection" / "assets_manifest.json"
    text = assets.read_text(encoding="utf-8") if assets.exists() else ""
    parent_outside = tmp_path / "parent-outside"
    parent_outside.mkdir()
    _tools_file(parent_outside / "tools.json", "SECRET-PARENT")
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(parent_outside)
    try:
        run_pipeline(
            "c1",
            "topic",
            "mission-2",
            runtime,
            channels,
            workflows,
            linked_parent / "tools.json",
        )
        err2 = None
    except ValueError as exc:
        err2 = str(exc)
    assets2 = runtime / "c1" / "mission-2" / "asset-selection" / "assets_manifest.json"
    text2 = assets2.read_text(encoding="utf-8") if assets2.exists() else ""
    cli_outside = tmp_path / "cli-tools.json"
    _tools_file(cli_outside, "SECRET-CLI")
    cli_link = tmp_path / "cli-tools-link.json"
    cli_link.symlink_to(cli_outside)
    monkeypatch.setattr(sys, "argv", [
        "run_content_production_pipeline.py",
        "--channel-id", "c1",
        "--topic", "topic",
        "--mission-id", "mission-3",
        "--runtime-dir", str(runtime),
        "--config", str(channels),
        "--workflows-config", str(workflows),
        "--tools-config", str(cli_link),
    ])
    try:
        main()
        err3 = None
    except ValueError as exc:
        err3 = str(exc)
    assets3 = runtime / "c1" / "mission-3" / "asset-selection" / "assets_manifest.json"
    text3 = assets3.read_text(encoding="utf-8") if assets3.exists() else ""
    assert (
        err,
        "SECRET-TOOLS" in text,
        err2,
        "SECRET-PARENT" in text2,
        err3,
        "SECRET-CLI" in text3,
    ) == (
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        False,
    )
    assert "SECRET-TOOLS" in outside.read_text(encoding="utf-8")

def test_manifest_does_not_follow_a_symlink(tmp_path):
    runtime = tmp_path / "runtime"
    channels = tmp_path / "channels.json"
    _channel_file(channels, "FruitKI")
    workflows = tmp_path / "workflows.json"
    _workflow_file(workflows, [])
    tools = tmp_path / "tools.json"
    mission = runtime / "c1" / "mission-1"
    mission.mkdir(parents=True)
    outside = tmp_path / "outside-manifest.json"
    outside.write_text('{"marker":"SECRET-MANIFEST"}\n', encoding="utf-8")
    (mission / "manifest.json").symlink_to(outside)
    try:
        run_pipeline("c1", "topic", "mission-1", runtime, channels, workflows, tools)
        err = None
    except ValueError as exc:
        err = str(exc)
    parent_outside = tmp_path / "parent-outside"
    parent_outside.mkdir()
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    (parent_outside / "manifest.json").write_text('{"marker":"SECRET-PARENT"}\n', encoding="utf-8")
    (runtime / "c1" / "mission-2").symlink_to(parent_outside)
    try:
        run_pipeline("c1", "topic", "mission-2", runtime, channels, workflows, tools)
        err2 = None
    except ValueError as exc:
        err2 = str(exc)
    assert (
        err,
        "SECRET-MANIFEST" in outside.read_text(encoding="utf-8"),
        err2,
        "SECRET-PARENT" in (parent_outside / "manifest.json").read_text(encoding="utf-8"),
    ) == (
        "refusing to follow a symlink",
        True,
        "refusing to follow a symlink",
        True,
    )
