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


def test_config_does_not_follow_a_symlink(tmp_path):
    workflows = tmp_path / "workflows.json"
    workflows.write_text(json.dumps({"workflows": [{"workflow_id": "fruitki-youtube"}]}), encoding="utf-8")
    kept = '{"channels":[],"marker":"keep"}\n'

    def library(config):
        try:
            rsc.register_channel(
                platform="YOUTUBE",
                channel_label="Fruit Channel",
                content_project="FruitKI",
                config_path=config,
                workflows_path=workflows,
            )
            return None
        except SystemExit as exc:
            return str(exc)

    def cli(config):
        argv = [
            "prog", "--platform", "YOUTUBE", "--label", "Fruit Channel",
            "--project", "FruitKI", "--config", str(config),
            "--workflows-config", str(workflows),
        ]
        with patch("sys.argv", argv):
            try:
                rsc.main()
                return None
            except SystemExit as exc:
                return str(exc)

    outside = tmp_path / "outside-channels.json"
    outside.write_text(kept, encoding="utf-8")
    linked = tmp_path / "linked-channels.json"
    linked.symlink_to(outside)
    parent_real = tmp_path / "parent-real"
    parent_real.mkdir()
    nested = parent_real / "channels.json"
    nested.write_text(kept, encoding="utf-8")
    parent_link = tmp_path / "parent-link"
    parent_link.symlink_to(parent_real)
    plain = tmp_path / "plain-channels.json"

    err_lib = library(linked)
    err_cli = cli(linked)
    err_parent = library(parent_link / "channels.json")
    err_plain = library(plain)
    plain_body = plain.read_text(encoding="utf-8") if plain.exists() else ""
    refused = "CHANNEL_REGISTRATION_ERROR: refusing to follow a symlink"
    assert (
        err_lib == refused and outside.read_text(encoding="utf-8") == kept
        and err_cli == refused and outside.read_text(encoding="utf-8") == kept
        and err_parent == refused and nested.read_text(encoding="utf-8") == kept
        and err_plain is None and "chan-yt-fruit-channel" in plain_body
        and linked.is_symlink() and parent_link.is_symlink()
    ), (
        err_lib, outside.read_text(encoding="utf-8"),
        err_cli, err_parent, nested.read_text(encoding="utf-8"),
        err_plain, plain_body,
    )


def test_workflows_config_does_not_follow_a_symlink(tmp_path):
    outside = tmp_path / "outside-workflows.json"
    outside.write_text(
        json.dumps({"workflows": [{"workflow_id": "other-only"}]}),
        encoding="utf-8",
    )
    linked = tmp_path / "linked-workflows.json"
    linked.symlink_to(outside)
    parent_real = tmp_path / "parent-real"
    parent_real.mkdir()
    (parent_real / "workflows.json").write_text(
        json.dumps({"workflows": [{"workflow_id": "other-only"}]}),
        encoding="utf-8",
    )
    parent_link = tmp_path / "parent-link"
    parent_link.symlink_to(parent_real)
    real_wf = tmp_path / "real-workflows.json"
    real_wf.write_text(
        json.dumps({"workflows": [{"workflow_id": "fruitki-youtube"}]}),
        encoding="utf-8",
    )

    def library(wf, cfg):
        try:
            rsc.register_channel(
                platform="YOUTUBE",
                channel_label="Fruit Channel",
                content_project="FruitKI",
                workflow_id="fruitki-youtube",
                config_path=cfg,
                workflows_path=wf,
            )
            return None
        except SystemExit as exc:
            return str(exc)

    def cli(wf, cfg):
        argv = [
            "prog", "--platform", "YOUTUBE", "--label", "Fruit Channel",
            "--project", "FruitKI", "--workflow", "fruitki-youtube",
            "--config", str(cfg), "--workflows-config", str(wf),
        ]
        with patch("sys.argv", argv):
            try:
                rsc.main()
                return None
            except SystemExit as exc:
                return str(exc)

    cfg_link = tmp_path / "cfg-link.json"
    cfg_parent = tmp_path / "cfg-parent.json"
    cfg_cli = tmp_path / "cfg-cli.json"
    cfg_real = tmp_path / "cfg-real.json"
    err_link = library(linked, cfg_link)
    err_parent = library(parent_link / "workflows.json", cfg_parent)
    err_cli = cli(linked, cfg_cli)
    err_real = library(real_wf, cfg_real)
    real_body = cfg_real.read_text(encoding="utf-8") if cfg_real.exists() else ""
    refused = "CHANNEL_REGISTRATION_ERROR: refusing to follow a symlink"
    assert (
        err_link == refused and not cfg_link.exists()
        and err_parent == refused and not cfg_parent.exists()
        and err_cli == refused and not cfg_cli.exists()
        and err_real is None and "chan-yt-fruit-channel" in real_body
        and linked.is_symlink() and parent_link.is_symlink()
        and outside.read_text(encoding="utf-8").find("other-only") >= 0
    ), (
        err_link, cfg_link.exists(), err_parent, cfg_parent.exists(),
        err_cli, cfg_cli.exists(), err_real, "chan-yt-fruit-channel" in real_body,
    )
