import pytest
import json
from pathlib import Path
from scripts.build_channel_workflow_tasks import build_workflow_tasks_for_channel

def test_build_workflow_tasks(tmp_path):
    queue_dir = tmp_path / "queue"
    queue_dir.mkdir()
    
    channels_path = tmp_path / "channels.json"
    workflows_path = tmp_path / "workflows.json"
    
    channels_path.write_text(json.dumps({
        "channels": [
            {
                "channel_id": "chan-test",
                "channel_label": "Test Channel",
                "platform": "YOUTUBE",
                "production_enabled": True,
                "workflow_id": "wf-1"
            }
        ]
    }))
    
    workflows_path.write_text(json.dumps({
        "workflows": [
            {
                "workflow_id": "wf-1",
                "production_steps": ["Write Script", "Generate Video"]
            }
        ]
    }))
    
    tasks = build_workflow_tasks_for_channel(
        channel_id="chan-test",
        topic="daily-test",
        queue_dir=queue_dir,
        channels_path=channels_path,
        workflows_path=workflows_path
    )
    
    assert len(tasks) == 2
    assert tasks[0]["instruction"] == "Execute workflow stage [Write Script] for channel [Test Channel] on platform [YOUTUBE]. Topic: daily-test."
    assert tasks[0]["project"] == "FruitKI-YouTube"
    
    assert tasks[1]["instruction"] == "Execute workflow stage [Generate Video] for channel [Test Channel] on platform [YOUTUBE]. Topic: daily-test."
    
    # Check deduplication
    tasks2 = build_workflow_tasks_for_channel(
        channel_id="chan-test",
        topic="daily-test",
        queue_dir=queue_dir,
        channels_path=channels_path,
        workflows_path=workflows_path
    )
    assert len(tasks2) == 0  # Should be deduped since they are in queue with QUEUED status

def test_build_workflow_tasks_disabled(tmp_path):
    queue_dir = tmp_path / "queue"
    channels_path = tmp_path / "channels.json"
    workflows_path = tmp_path / "workflows.json"
    
    channels_path.write_text(json.dumps({
        "channels": [
            {
                "channel_id": "chan-test",
                "production_enabled": False,
                "workflow_id": "wf-1"
            }
        ]
    }))
    
    workflows_path.write_text(json.dumps({
        "workflows": [{"workflow_id": "wf-1"}]
    }))
    
    with pytest.raises(ValueError, match="production_enabled=False"):
        build_workflow_tasks_for_channel(
            channel_id="chan-test",
            queue_dir=queue_dir,
            channels_path=channels_path,
            workflows_path=workflows_path
        )
