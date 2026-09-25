import pytest
import os
import sys
import json
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import build_channel_workflow_tasks

@pytest.fixture
def test_data(tmp_path):
    channels = tmp_path / "channels.json"
    channels.write_text(json.dumps({
        "channels": [
            {
                "channel_id": "chan-yt-test",
                "channel_label": "YT Test",
                "platform": "YOUTUBE",
                "workflow_id": "wf-yt-basic",
                "production_enabled": True
            },
            {
                "channel_id": "chan-disabled",
                "workflow_id": "wf-yt-basic",
                "production_enabled": False
            }
        ]
    }))
    
    workflows = tmp_path / "workflows.json"
    workflows.write_text(json.dumps({
        "workflows": [
            {
                "workflow_id": "wf-yt-basic",
                "production_steps": ["Script", "Audio", "Video"]
            }
        ]
    }))
    
    queue = tmp_path / "queue"
    queue.mkdir()
    
    return channels, workflows, queue

def test_map_project_name():
    assert build_channel_workflow_tasks.map_project_name("FruitKI", "YOUTUBE") == "FruitKI-YouTube"
    assert build_channel_workflow_tasks.map_project_name("", "TIKTOK") == "3D-KI-TikTok"
    assert build_channel_workflow_tasks.map_project_name("Unknown", "INSTA") == "2026-courier"

def test_slugify():
    assert build_channel_workflow_tasks.slugify("Hello World!") == "hello-world"
    assert build_channel_workflow_tasks.slugify("  Lots of   Spaces  ") == "lots-of-spaces"

def test_build_success(test_data):
    ch, wf, q = test_data
    
    tasks = build_channel_workflow_tasks.build_workflow_tasks_for_channel(
        channel_id="chan-yt-test",
        topic="My Topic",
        priority=2,
        queue_dir=q,
        channels_path=ch,
        workflows_path=wf
    )
    
    assert len(tasks) == 3
    assert tasks[0]["status"] == "QUEUED"
    assert tasks[0]["priority"] == 2
    assert "Script" in tasks[0]["instruction"]
    assert tasks[1]["parent_task_id"] == tasks[0]["task_id"]
    
    assert (q / f"{tasks[0]['task_id']}.json").exists()

def test_build_disabled(test_data):
    ch, wf, q = test_data
    with pytest.raises(ValueError) as exc:
        build_channel_workflow_tasks.build_workflow_tasks_for_channel(
            channel_id="chan-disabled",
            queue_dir=q,
            channels_path=ch,
            workflows_path=wf
        )
    assert "production_enabled=False" in str(exc.value)

def test_build_dedup(test_data):
    ch, wf, q = test_data
    
    # Run once
    tasks1 = build_channel_workflow_tasks.build_workflow_tasks_for_channel(
        channel_id="chan-yt-test",
        topic="My Topic",
        queue_dir=q,
        channels_path=ch,
        workflows_path=wf
    )
    assert len(tasks1) == 3
    
    # Run twice
    tasks2 = build_channel_workflow_tasks.build_workflow_tasks_for_channel(
        channel_id="chan-yt-test",
        topic="My Topic",
        queue_dir=q,
        channels_path=ch,
        workflows_path=wf
    )
    assert len(tasks2) == 0 # deduped
    
def test_main(test_data, capsys):
    ch, wf, q = test_data
    with mock.patch.object(sys, 'argv', ['prog', '--channel-id', 'chan-yt-test', '--topic', 'Top', '--queue-dir', str(q), '--config', str(ch), '--workflows-config', str(wf)]):
        build_channel_workflow_tasks.main()
        
    captured = capsys.readouterr()
    assert "Generated 3 workflow tasks" in captured.out

