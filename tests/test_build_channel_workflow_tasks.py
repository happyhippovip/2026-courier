import json
import sys
from pathlib import Path
import pytest

from scripts.build_channel_workflow_tasks import build_workflow_tasks_for_channel, main


@pytest.fixture
def test_configs(tmp_path: Path):
    cfg_file = tmp_path / "social_channels.json"
    wf_file = tmp_path / "content_workflows.json"

    channels_data = {
        "channels": [
            {
                "channel_id": "chan-yt-fruitki",
                "platform": "YOUTUBE",
                "channel_label": "FruitKI Channel",
                "content_project": "FruitKI",
                "workflow_id": "fruitki-youtube",
                "production_enabled": True,
            },
            {
                "channel_id": "chan-disabled",
                "platform": "YOUTUBE",
                "channel_label": "Disabled Channel",
                "content_project": "FruitKI",
                "workflow_id": "fruitki-youtube",
                "production_enabled": False,
            },
        ]
    }
    workflows_data = {
        "workflows": [
            {
                "workflow_id": "fruitki-youtube",
                "production_steps": ["IDEA_PROMPT", "SCRIPT_GEN", "RENDER_SCENE"],
            }
        ]
    }

    cfg_file.write_text(json.dumps(channels_data), encoding="utf-8")
    wf_file.write_text(json.dumps(workflows_data), encoding="utf-8")
    return cfg_file, wf_file


def test_build_workflow_tasks_success(tmp_path: Path, test_configs):
    cfg_file, wf_file = test_configs
    q_dir = tmp_path / "night-queue"

    tasks = build_workflow_tasks_for_channel(
        channel_id="chan-yt-fruitki",
        topic="apple-harvest-2026",
        priority=0,
        queue_dir=q_dir,
        channels_path=cfg_file,
        workflows_path=wf_file,
        quiet=True,
    )

    assert len(tasks) == 3
    assert tasks[0]["task_id"].startswith("TASK-YT-FRUITKI-APPLE-HARVEST-2026-")
    assert tasks[0]["project"] == "FruitKI-YouTube"
    assert tasks[0]["status"] == "QUEUED"
    assert tasks[0]["priority"] == 0

    # Chaining parent_task_id
    assert tasks[0]["parent_task_id"] is None
    assert tasks[1]["parent_task_id"] == tasks[0]["task_id"]
    assert tasks[2]["parent_task_id"] == tasks[1]["task_id"]

    # Verify atomic writes on disk
    task_file = q_dir / f"{tasks[0]['task_id']}.json"
    assert task_file.is_file()
    saved = json.loads(task_file.read_text(encoding="utf-8"))
    assert saved["task_id"] == tasks[0]["task_id"]


def test_build_workflow_tasks_dedup(tmp_path: Path, test_configs):
    cfg_file, wf_file = test_configs
    q_dir = tmp_path / "night-queue"

    # First run generates 3 tasks
    tasks1 = build_workflow_tasks_for_channel(
        channel_id="chan-yt-fruitki",
        topic="apple-harvest-2026",
        queue_dir=q_dir,
        channels_path=cfg_file,
        workflows_path=wf_file,
        quiet=True,
    )
    assert len(tasks1) == 3

    # Second run should skip all existing tasks
    tasks2 = build_workflow_tasks_for_channel(
        channel_id="chan-yt-fruitki",
        topic="apple-harvest-2026",
        queue_dir=q_dir,
        channels_path=cfg_file,
        workflows_path=wf_file,
        quiet=True,
    )
    assert len(tasks2) == 0


def test_build_workflow_tasks_dry_run_and_disabled(tmp_path: Path, test_configs):
    cfg_file, wf_file = test_configs
    q_dir = tmp_path / "night-queue"

    # Dry run should not write to disk
    tasks = build_workflow_tasks_for_channel(
        channel_id="chan-yt-fruitki",
        topic="dry-run-topic",
        queue_dir=q_dir,
        channels_path=cfg_file,
        workflows_path=wf_file,
        dry_run=True,
        quiet=True,
    )
    assert len(tasks) == 3
    assert not (q_dir / f"{tasks[0]['task_id']}.json").exists()

    # Disabled channel raises ValueError
    with pytest.raises(ValueError, match="production_enabled=False"):
        build_workflow_tasks_for_channel(
            channel_id="chan-disabled",
            queue_dir=q_dir,
            channels_path=cfg_file,
            workflows_path=wf_file,
            quiet=True,
        )


def test_build_workflow_tasks_cli(tmp_path: Path, test_configs, capsys, monkeypatch):
    cfg_file, wf_file = test_configs
    q_dir = tmp_path / "night-queue"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_channel_workflow_tasks.py",
            "--channel-id", "chan-yt-fruitki",
            "--topic", "cli-test",
            "--queue-dir", str(q_dir),
            "--config", str(cfg_file),
            "--workflows-config", str(wf_file),
            "--dry-run",
            "--json",
        ],
    )
    main()
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert len(res) == 3
    assert "TASK-YT-FRUITKI-CLI-TEST-" in res[0]["task_id"]
