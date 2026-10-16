"""Unit test for Human Publish Gate in scripts/run_content_production_pipeline.py."""
import json
import pytest
from pathlib import Path
from scripts.run_content_production_pipeline import run_pipeline


@pytest.fixture
def mock_pipeline_env(tmp_path):
    channels_path = tmp_path / "channels.json"
    workflows_path = tmp_path / "workflows.json"
    tools_path = tmp_path / "tools.json"

    channels_data = {
        "channels": [
            {
                "channel_id": "chan-test-gate",
                "platform": "YOUTUBE",
                "content_project": "FruitKI",
                "workflow_id": "wf-test-gate"
            }
        ]
    }
    workflows_data = {
        "workflows": [
            {
                "workflow_id": "wf-test-gate",
                "production_steps": ["IDEA", "READY_TO_PUBLISH"]
            }
        ]
    }
    tools_data = {"ffmpeg": {"installed": False}, "godot": {"installed": False}}

    channels_path.write_text(json.dumps(channels_data), encoding="utf-8")
    workflows_path.write_text(json.dumps(workflows_data), encoding="utf-8")
    tools_path.write_text(json.dumps(tools_data), encoding="utf-8")

    return {
        "runtime_dir": tmp_path / "runtime",
        "channels_path": channels_path,
        "workflows_path": workflows_path,
        "tools_path": tools_path,
    }


def test_human_publish_gate_pauses_without_approval(mock_pipeline_env):
    manifest = run_pipeline(
        channel_id="chan-test-gate",
        topic="test-gate-pause",
        runtime_dir=mock_pipeline_env["runtime_dir"],
        channels_path=mock_pipeline_env["channels_path"],
        workflows_path=mock_pipeline_env["workflows_path"],
        local_tools_path=mock_pipeline_env["tools_path"],
        approve_publish=False,
    )

    assert manifest["overall_status"] == "READY_TO_PUBLISH"
    ready_stage = manifest["stages"]["READY_TO_PUBLISH"]
    assert ready_stage["status"] == "AWAITING_HUMAN_APPROVAL"
    assert manifest["publish_package"]["status"] == "AWAITING_HUMAN_APPROVAL"


def test_human_publish_gate_resumes_with_approval(mock_pipeline_env):
    # Step 1: Run without approval -> Pauses at READY_TO_PUBLISH
    manifest1 = run_pipeline(
        channel_id="chan-test-gate",
        topic="test-gate-resume",
        runtime_dir=mock_pipeline_env["runtime_dir"],
        channels_path=mock_pipeline_env["channels_path"],
        workflows_path=mock_pipeline_env["workflows_path"],
        local_tools_path=mock_pipeline_env["tools_path"],
        approve_publish=False,
    )
    assert manifest1["overall_status"] == "READY_TO_PUBLISH"

    # Step 2: Resume with approval -> Completes pipeline
    manifest2 = run_pipeline(
        channel_id="chan-test-gate",
        topic="test-gate-resume",
        runtime_dir=mock_pipeline_env["runtime_dir"],
        channels_path=mock_pipeline_env["channels_path"],
        workflows_path=mock_pipeline_env["workflows_path"],
        local_tools_path=mock_pipeline_env["tools_path"],
        approve_publish=True,
    )
    assert manifest2["overall_status"] == "COMPLETED"
    ready_stage = manifest2["stages"]["READY_TO_PUBLISH"]
    assert ready_stage["status"] == "COMPLETED"
    assert manifest2["publish_package"]["status"] == "APPROVED_BY_HUMAN"
