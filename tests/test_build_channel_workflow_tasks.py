import pytest
import json
import argparse
from pathlib import Path

from scripts.build_channel_workflow_tasks import (
    load_json,
    save_json,
    slugify,
    map_project_name,
    build_workflow_tasks_for_channel,
    main
)

@pytest.fixture
def fake_configs(tmp_path):
    channels_path = tmp_path / "social_channels.json"
    workflows_path = tmp_path / "content_workflows.json"
    queue_dir = tmp_path / "night-queue"
    
    channels_data = {
        "channels": [
            {
                "channel_id": "chan-test-1",
                "channel_label": "Test Channel 1",
                "platform": "YOUTUBE",
                "content_project": "FruitKI",
                "production_enabled": True,
                "workflow_id": "wf-test-1"
            },
            {
                "channel_id": "chan-disabled",
                "production_enabled": False
            },
            {
                "channel_id": "chan-no-wf",
                "production_enabled": True,
                "workflow_id": "wf-unknown"
            }
        ]
    }
    
    workflows_data = {
        "workflows": [
            {
                "workflow_id": "wf-test-1",
                "production_steps": ["Script Writing", "Video Rendering"]
            }
        ]
    }
    
    channels_path.write_text(json.dumps(channels_data))
    workflows_path.write_text(json.dumps(workflows_data))
    
    return channels_path, workflows_path, queue_dir

def test_slugify():
    assert slugify("Hello World!") == "hello-world"
    assert slugify("  test  --- ") == "test"

def test_map_project_name():
    assert map_project_name("FruitKI", "YOUTUBE") == "FruitKI-YouTube"
    assert map_project_name("Unknown", "YOUTUBE") == "FruitKI-YouTube"
    assert map_project_name("3D-KI-Videos", "TIKTOK") == "3D-KI-TikTok"
    assert map_project_name("Unknown", "TIKTOK") == "3D-KI-TikTok"
    assert map_project_name("Unknown", "INSTAGRAM") == "2026-courier"

def test_build_workflow_missing_files(tmp_path):
    with pytest.raises(FileNotFoundError, match="Channel registry not found"):
        build_workflow_tasks_for_channel("chan-test-1", channels_path=tmp_path / "missing", workflows_path=tmp_path)
        
    channels_path = tmp_path / "chan.json"
    channels_path.write_text("{}")
    
    with pytest.raises(FileNotFoundError, match="Workflow registry not found"):
        build_workflow_tasks_for_channel("chan-test-1", channels_path=channels_path, workflows_path=tmp_path / "missing")

def test_build_workflow_invalid_channel(fake_configs):
    ch, wf, qd = fake_configs
    with pytest.raises(ValueError, match="not found in"):
        build_workflow_tasks_for_channel("missing-chan", channels_path=ch, workflows_path=wf, queue_dir=qd)
        
    with pytest.raises(ValueError, match="production_enabled=False"):
        build_workflow_tasks_for_channel("chan-disabled", channels_path=ch, workflows_path=wf, queue_dir=qd)
        
    with pytest.raises(ValueError, match="Workflow 'wf-unknown'"):
        build_workflow_tasks_for_channel("chan-no-wf", channels_path=ch, workflows_path=wf, queue_dir=qd)

def test_build_workflow_success_and_dedupe(fake_configs):
    ch, wf, qd = fake_configs
    
    # First creation
    tasks = build_workflow_tasks_for_channel(
        "chan-test-1", "topic-x", priority=0, queue_dir=qd, channels_path=ch, workflows_path=wf
    )
    
    assert len(tasks) == 2
    assert tasks[0]["task_id"] == "TASK-TEST-1-TOPIC-X-SCRIPT-WRITING"
    assert tasks[0]["project"] == "FruitKI-YouTube"
    assert tasks[0]["priority"] == 0
    assert tasks[0]["parent_task_id"] is None
    
    assert tasks[1]["task_id"] == "TASK-TEST-1-TOPIC-X-VIDEO-RENDERING"
    assert tasks[1]["parent_task_id"] == "TASK-TEST-1-TOPIC-X-SCRIPT-WRITING"
    
    # Dedupe creation - files exist with status QUEUED
    tasks2 = build_workflow_tasks_for_channel(
        "chan-test-1", "topic-x", queue_dir=qd, channels_path=ch, workflows_path=wf
    )
    assert len(tasks2) == 0

def test_main(monkeypatch, fake_configs, capsys):
    ch, wf, qd = fake_configs
    
    test_args = [
        "prog",
        "--channel-id", "chan-test-1",
        "--topic", "cli-topic",
        "--priority", "2",
        "--queue-dir", str(qd),
        "--config", str(ch),
        "--workflows-config", str(wf)
    ]
    
    monkeypatch.setattr("sys.argv", test_args)
    main()
    
    out, _ = capsys.readouterr()
    assert "Generated 2 workflow tasks" in out
    
    # Run again for dedupe
    main()
    out2, _ = capsys.readouterr()
    assert "Generated 0 workflow tasks" in out2
