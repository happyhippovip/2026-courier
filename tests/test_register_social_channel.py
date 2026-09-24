import json
import os
import sys
from pathlib import Path
import pytest

from scripts.register_social_channel import (
    register_channel,
    slugify,
    check_secrets,
    ChannelRegistrationError,
    main,
)


def test_slugify():
    assert slugify("Fruit KI Official") == "fruit-ki-official"
    assert slugify("Test!!!Channel---123") == "test-channel-123"


def test_register_channel_success(tmp_path: Path):
    cfg_file = tmp_path / "social_channels.json"
    wf_file = tmp_path / "content_workflows.json"
    wf_file.write_text(json.dumps({"workflows": [{"workflow_id": "fruitki-youtube"}]}), encoding="utf-8")

    chan = register_channel(
        platform="YOUTUBE",
        channel_label="FruitKI Channel",
        content_project="FruitKI",
        config_path=cfg_file,
        workflows_path=wf_file,
    )

    assert chan["channel_id"] == "chan-yt-fruitki-channel"
    assert chan["platform"] == "YOUTUBE"
    if os.name == "nt":
        assert chan["credential_reference_metadata"].startswith("WINDOWS_KEYRING_YOUTUBE_")
    else:
        assert chan["credential_reference_metadata"].startswith("MACOS_KEYCHAIN_YOUTUBE_")

    # Verify atomic file creation
    assert cfg_file.is_file()
    registry = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert len(registry["channels"]) == 1
    assert registry["channels"][0]["channel_id"] == "chan-yt-fruitki-channel"


def test_register_channel_duplicate_fails(tmp_path: Path):
    cfg_file = tmp_path / "social_channels.json"
    wf_file = tmp_path / "content_workflows.json"
    wf_file.write_text(json.dumps({"workflows": []}), encoding="utf-8")

    register_channel(
        platform="TIKTOK",
        channel_label="Daily Memes",
        workflow_id="generic-staging-workflow",
        config_path=cfg_file,
        workflows_path=wf_file,
    )

    with pytest.raises(ChannelRegistrationError, match="already registered"):
        register_channel(
            platform="TIKTOK",
            channel_label="Daily Memes",
            workflow_id="generic-staging-workflow",
            config_path=cfg_file,
            workflows_path=wf_file,
        )


def test_secret_detection_blocks_registration(tmp_path: Path):
    cfg_file = tmp_path / "social_channels.json"
    wf_file = tmp_path / "content_workflows.json"

    with pytest.raises(ChannelRegistrationError, match="Sensitive credential"):
        register_channel(
            platform="YOUTUBE",
            channel_label="sk-1234567890abcdef12345678",
            config_path=cfg_file,
            workflows_path=wf_file,
        )


def test_register_social_channel_cli(tmp_path: Path, capsys, monkeypatch):
    cfg_file = tmp_path / "social_channels.json"
    wf_file = tmp_path / "content_workflows.json"
    wf_file.write_text(json.dumps({"workflows": []}), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "register_social_channel.py",
            "--platform", "TIKTOK",
            "--label", "Cool 3D",
            "--workflow", "generic-staging-workflow",
            "--config", str(cfg_file),
            "--workflows-config", str(wf_file),
        ],
    )
    main()
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["channel_id"] == "chan-tt-cool-3d"
    assert res["platform"] == "TIKTOK"
