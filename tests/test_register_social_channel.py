import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import scripts.register_social_channel as rsc

def test_slugify():
    assert rsc.slugify("My Cool Channel 123!") == "my-cool-channel-123"
    assert rsc.slugify("---test--") == "test"

def test_check_secrets():
    # Should not raise
    rsc.check_secrets("This is a normal text without secrets.")
    
    # Should raise SystemExit
    with pytest.raises(SystemExit) as exc:
        rsc.check_secrets("password: 'supersecret'")
    assert "CHANNEL_REGISTRATION_ERROR" in str(exc.value)

    with pytest.raises(SystemExit) as exc:
        rsc.check_secrets("Here is a token: ghp_123456789012345678901234567890")

def test_register_channel_success(tmp_path):
    config_path = tmp_path / "social_channels.json"
    workflows_path = tmp_path / "content_workflows.json"
    
    # Provide valid workflows
    workflows_path.write_text(json.dumps({"workflows": [{"workflow_id": "fruitki-youtube"}]}))

    result = rsc.register_channel(
        platform="YOUTUBE",
        channel_label="Fruit Channel",
        content_project="FruitKI",
        config_path=config_path,
        workflows_path=workflows_path
    )

    assert result["platform"] == "YOUTUBE"
    assert result["channel_id"] == "chan-yt-fruit-channel"
    assert result["workflow_id"] == "fruitki-youtube"

    # Verify JSON was written
    saved = json.loads(config_path.read_text())
    assert len(saved["channels"]) == 1
    assert saved["channels"][0]["channel_id"] == "chan-yt-fruit-channel"

def test_register_channel_unsupported_platform(tmp_path):
    with pytest.raises(SystemExit) as exc:
        rsc.register_channel(
            platform="INSTAGRAM",
            channel_label="My Insta",
            config_path=tmp_path / "social_channels.json",
            workflows_path=tmp_path / "content_workflows.json"
        )
    assert "Unsupported platform" in str(exc.value)

def test_register_channel_duplicate(tmp_path):
    config_path = tmp_path / "social_channels.json"
    
    # Pre-populate with duplicate
    config_path.write_text(json.dumps({
        "channels": [{"channel_id": "chan-yt-test-channel"}]
    }))

    with pytest.raises(SystemExit) as exc:
        rsc.register_channel(
            platform="YOUTUBE",
            channel_label="Test Channel",
            config_path=config_path,
            workflows_path=tmp_path / "content_workflows.json"
        )
    assert "already registered" in str(exc.value)

def test_register_channel_invalid_workflow(tmp_path):
    workflows_path = tmp_path / "content_workflows.json"
    workflows_path.write_text(json.dumps({"workflows": [{"workflow_id": "other-workflow"}]}))

    with pytest.raises(SystemExit) as exc:
        rsc.register_channel(
            platform="YOUTUBE",
            channel_label="Test Channel",
            workflow_id="invalid-workflow",
            config_path=tmp_path / "social_channels.json",
            workflows_path=workflows_path
        )
    assert "not defined in" in str(exc.value)

@patch("sys.argv", ["register_social_channel.py", "--platform", "TIKTOK", "--label", "TikTok Channel", "--project", "3D-KI-TikTok", "--config", "tmp_config.json", "--workflows-config", "tmp_wf.json"])
@patch("scripts.register_social_channel.register_channel")
def test_main(mock_register):
    mock_register.return_value = {"status": "ok"}
    rsc.main()
    mock_register.assert_called_once()
    assert mock_register.call_args[1]["platform"] == "TIKTOK"

def test_register_channel_short_label(tmp_path):
    with pytest.raises(SystemExit) as exc:
        rsc.register_channel(
            platform="YOUTUBE",
            channel_label="A",
            config_path=tmp_path / "social_channels.json",
            workflows_path=tmp_path / "content_workflows.json"
        )
    assert "channel_label must have at least 2 characters" in str(exc.value)

def test_register_channel_auto_workflow_tiktok(tmp_path):
    config_path = tmp_path / "social_channels.json"
    workflows_path = tmp_path / "content_workflows.json"
    workflows_path.write_text(json.dumps({"workflows": [{"workflow_id": "3d-ai-tiktok"}]}))

    result = rsc.register_channel(
        platform="TIKTOK",
        channel_label="My TikTok",
        content_project="3D-KI-TikTok",
        config_path=config_path,
        workflows_path=workflows_path
    )
    assert result["workflow_id"] == "3d-ai-tiktok"

def test_register_channel_bad_workflow_json(tmp_path):
    # Coverage for `except Exception:` block where JSON is invalid
    config_path = tmp_path / "social_channels.json"
    workflows_path = tmp_path / "content_workflows.json"
    workflows_path.write_text("invalid json")

    result = rsc.register_channel(
        platform="YOUTUBE",
        channel_label="Valid Label",
        workflow_id="fruitki-youtube", # Skips the known_wfs check because parsing fails and we pass
        config_path=config_path,
        workflows_path=workflows_path
    )
    assert result["workflow_id"] == "fruitki-youtube"
