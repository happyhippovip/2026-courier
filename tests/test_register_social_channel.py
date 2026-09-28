import pytest
import json
from pathlib import Path
from scripts.register_social_channel import register_channel, fail, check_secrets

def test_register_channel_success(tmp_path):
    channels_config = tmp_path / "social_channels.json"
    workflows_config = tmp_path / "content_workflows.json"
    
    workflows_config.write_text(json.dumps({
        "workflows": [
            {"workflow_id": "generic-staging-workflow"}
        ]
    }))
    
    channel = register_channel(
        platform="YOUTUBE",
        channel_label="Test YouTube",
        content_project="FruitKI",
        workflow_id="generic-staging-workflow",
        config_path=channels_config,
        workflows_path=workflows_config
    )
    
    assert channel["platform"] == "YOUTUBE"
    assert channel["channel_id"] == "chan-yt-test-youtube"
    
    # Check that file was written
    saved = json.loads(channels_config.read_text())
    assert len(saved["channels"]) == 1
    assert saved["channels"][0]["channel_id"] == "chan-yt-test-youtube"

def test_register_channel_duplicate(tmp_path):
    channels_config = tmp_path / "social_channels.json"
    channels_config.write_text(json.dumps({
        "channels": [
            {"channel_id": "chan-tt-test"}
        ]
    }))
    
    with pytest.raises(SystemExit, match="CHANNEL_REGISTRATION_ERROR"):
        register_channel(
            platform="TIKTOK",
            channel_label="test",
            config_path=channels_config,
            workflows_path=tmp_path / "workflows.json"
        )

def test_check_secrets():
    with pytest.raises(SystemExit, match="Sensitive credential or secret pattern"):
        check_secrets("password='SuperSecretPassword123'")
        
    with pytest.raises(SystemExit, match="Sensitive credential or secret pattern"):
        check_secrets("ghp_123456789012345678901234567890123456")
        
    # Should not raise
    check_secrets("No secrets here, just plain text")

def test_register_channel_with_secrets(tmp_path):
    with pytest.raises(SystemExit, match="Sensitive credential or secret pattern"):
        register_channel(
            platform="YOUTUBE",
            channel_label="Test ghp_123456789012345678901234567890123456",
            config_path=tmp_path / "channels.json",
            workflows_path=tmp_path / "workflows.json"
        )

