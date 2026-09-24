"""Unit tests for Cross-Platform Godot and FFmpeg bindings in content pipeline."""
import json
from pathlib import Path
from scripts.run_content_production_pipeline import (
    discover_godot_binary,
    discover_ffmpeg_binary,
    resolve_godot_project_binding,
    run_pipeline,
)


def test_discover_godot_binary():
    bin_path, version = discover_godot_binary()
    assert bin_path is not None
    assert Path(bin_path).exists()
    assert version is not None
    assert "4." in version


def test_discover_ffmpeg_binary():
    ffmpeg_bin = discover_ffmpeg_binary()
    assert ffmpeg_bin is not None
    assert Path(ffmpeg_bin).exists()


def test_resolve_godot_project_binding():
    local_tools = {"project_bindings": {}}
    bound_path, default_scene = resolve_godot_project_binding("FruitKI", local_tools)
    assert bound_path is not None
    assert (Path(bound_path) / "project.godot").is_file()
    assert default_scene == "res://strawberry_school_short.tscn"


def test_pipeline_video_build_bound_and_verified(tmp_path):
    channels_path = tmp_path / "channels.json"
    workflows_path = tmp_path / "workflows.json"
    tools_path = tmp_path / "tools.json"

    channels_data = {
        "channels": [
            {
                "channel_id": "chan-test-binding",
                "platform": "YOUTUBE",
                "content_project": "FruitKI",
                "workflow_id": "wf-test-binding"
            }
        ]
    }
    workflows_data = {
        "workflows": [
            {
                "workflow_id": "wf-test-binding",
                "production_steps": ["IDEA", "ASSET_SELECTION", "VIDEO_BUILD", "READY_TO_PUBLISH"]
            }
        ]
    }
    tools_data = {"tools": {}, "project_bindings": {}}

    channels_path.write_text(json.dumps(channels_data), encoding="utf-8")
    workflows_path.write_text(json.dumps(workflows_data), encoding="utf-8")
    tools_path.write_text(json.dumps(tools_data), encoding="utf-8")

    manifest = run_pipeline(
        channel_id="chan-test-binding",
        topic="strawberry-school-test",
        runtime_dir=tmp_path / "runtime",
        channels_path=channels_path,
        workflows_path=workflows_path,
        local_tools_path=tools_path,
        approve_publish=False,
    )

    assert manifest["stages"]["ASSET_SELECTION"]["status"] == "COMPLETED"
    mission_dir = tmp_path / "runtime" / "chan-test-binding" / "prod-test-binding-strawberry-school-test"
    assets_file = mission_dir / manifest["stages"]["ASSET_SELECTION"]["artifact_path"]
    assets_manifest = json.loads(assets_file.read_text(encoding="utf-8"))
    assert assets_manifest["godot_project_binding"]["status"] == "BOUND_READ_ONLY"

    assert manifest["stages"]["VIDEO_BUILD"]["status"] == "COMPLETED"
    video_details = manifest["stages"]["VIDEO_BUILD"]["details"]
    assert video_details["godot_binary_found"] is True
    assert video_details["godot_project_bound"] is True
    assert video_details["godot_real_3d_render"]["status"] == "BOUND_AND_VERIFIED"
