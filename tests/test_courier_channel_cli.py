import json
import pytest
from pathlib import Path
import sys

# Ensure scripts dir on path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from courier_channel_cli import main


def test_cli_channels(capsys):
    ret = main(["channels"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "chan-yt-fruitki" in captured.out
    assert "chan-tt-3d-ai" in captured.out


def test_cli_channels_json(capsys):
    ret = main(["channels", "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)
    assert len(data) >= 2


def test_cli_check_auth_dry_run(capsys):
    ret = main(["check-auth", "--dry-run"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "DRY_RUN_OK" in captured.out
    assert "Zero-Cost Policy: 0.00 EUR" in captured.out


def test_cli_status(capsys):
    ret = main(["status"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "[LOCAL ENGINE TOOLS]" in captured.out
    assert "[CHANNELS & PRODUCTION STATUS]" in captured.out
    assert "chan-yt-fruitki" in captured.out


def test_cli_queue(tmp_path, monkeypatch, capsys):
    # Route queue to tmp_path
    from build_channel_workflow_tasks import DEFAULT_QUEUE_DIR
    queue_dir = tmp_path / "night-queue"

    import build_channel_workflow_tasks
    monkeypatch.setattr(build_channel_workflow_tasks, "DEFAULT_QUEUE_DIR", queue_dir)

    # Use custom queue runner
    from build_channel_workflow_tasks import build_workflow_tasks_for_channel
    tasks = build_workflow_tasks_for_channel(
        channel_id="chan-yt-fruitki",
        topic="unit-test-topic",
        queue_dir=queue_dir
    )
    assert len(tasks) > 0
    assert any(t["task_id"].startswith("TASK-YT-FRUITKI-UNIT-TEST-TOPIC") for t in tasks)


def test_cli_run_and_approve(tmp_path, capsys):
    runtime_dir = tmp_path / "runtime"
    topic = "cli-test-short"
    channel_id = "chan-yt-fruitki"

    # 1. Run pipeline - must stop at human gate
    run_args = [
        "run",
        "--channel-id", channel_id,
        "--topic", topic,
        "--runtime-dir", str(runtime_dir)
    ]
    ret = main(run_args)
    assert ret == 0
    captured = capsys.readouterr()
    assert "READY_TO_PUBLISH" in captured.out

    manifest_file = runtime_dir / channel_id / f"prod-yt-fruitki-{topic}" / "manifest.json"
    assert manifest_file.exists()
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert data["overall_status"] == "READY_TO_PUBLISH"

    # 2. Approve stage
    app_args = [
        "approve",
        "--channel-id", channel_id,
        "--topic", topic,
        "--runtime-dir", str(runtime_dir)
    ]
    ret_app = main(app_args)
    assert ret_app == 0
    data_app = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert data_app["overall_status"] == "COMPLETED"
    assert data_app["stages"]["READY_TO_PUBLISH"]["status"] == "COMPLETED"
