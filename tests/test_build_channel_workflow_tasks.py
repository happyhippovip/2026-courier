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

def test_queue_dir_does_not_follow_a_symlink(tmp_path, fake_configs, monkeypatch):
    channels_path, workflows_path, _queue = fake_configs
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = tmp_path / "linked-queue"
    linked.symlink_to(outside, target_is_directory=True)

    parent_outside = tmp_path / "parent-outside"
    parent_outside.mkdir()
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(parent_outside, target_is_directory=True)

    def run(queue):
        try:
            build_workflow_tasks_for_channel(
                "chan-test-1",
                "topic-x",
                queue_dir=queue,
                channels_path=channels_path,
                workflows_path=workflows_path,
            )
        except ValueError as exc:
            return str(exc)
        return "wrote"

    lib_link = run(linked)
    leaked = sorted(p.name for p in outside.iterdir())
    lib_parent = run(linked_parent / "queue")
    parent_names = sorted(p.name for p in parent_outside.iterdir())
    plain = tmp_path / "plain-queue"
    plain_result = run(plain)
    plain_names = sorted(p.name for p in plain.iterdir()) if plain.exists() else []

    cli_outside = tmp_path / "cli-outside"
    cli_outside.mkdir()
    (cli_outside / "keep.txt").write_text("keep", encoding="utf-8")
    cli_link = tmp_path / "cli-linked"
    cli_link.symlink_to(cli_outside, target_is_directory=True)
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "--channel-id", "chan-test-1",
            "--topic", "cli-topic",
            "--queue-dir", str(cli_link),
            "--config", str(channels_path),
            "--workflows-config", str(workflows_path),
        ],
    )
    try:
        main()
        cli_err = None
    except ValueError as exc:
        cli_err = str(exc)
    cli_names = sorted(p.name for p in cli_outside.iterdir())
    assert (
        lib_link,
        leaked,
        lib_parent,
        parent_names,
        plain_result,
        plain_names,
        cli_err,
        cli_names,
    ) == (
        "refusing to follow a symlink",
        ["keep.txt"],
        "refusing to follow a symlink",
        ["keep.txt"],
        "wrote",
        [
            "TASK-TEST-1-TOPIC-X-SCRIPT-WRITING.json",
            "TASK-TEST-1-TOPIC-X-VIDEO-RENDERING.json",
        ],
        "refusing to follow a symlink",
        ["keep.txt"],
    )


def test_channels_config_does_not_follow_a_symlink(tmp_path, fake_configs, monkeypatch):
    _channels, workflows_path, _queue = fake_configs
    outside = tmp_path / "outside-channels.json"
    outside.write_text(json.dumps({
        "channels": [{
            "channel_id": "chan-secret",
            "channel_label": "SECRET-CHANNEL",
            "platform": "YOUTUBE",
            "content_project": "FruitKI",
            "production_enabled": True,
            "workflow_id": "wf-test-1",
        }]
    }), encoding="utf-8")
    link = tmp_path / "linked-channels.json"
    link.symlink_to(outside)

    parent_outside = tmp_path / "channels-parent-outside"
    parent_outside.mkdir()
    (parent_outside / "channels.json").write_text(outside.read_text(encoding="utf-8"), encoding="utf-8")
    linked_parent = tmp_path / "channels-linked-parent"
    linked_parent.symlink_to(parent_outside, target_is_directory=True)

    def run(config, name):
        queue = tmp_path / name
        try:
            build_workflow_tasks_for_channel(
                "chan-secret",
                "topic-x",
                queue_dir=queue,
                channels_path=config,
                workflows_path=workflows_path,
            )
            err = None
        except ValueError as exc:
            err = str(exc)
        names = sorted(p.name for p in queue.iterdir()) if queue.exists() else []
        body = (queue / names[0]).read_text(encoding="utf-8") if names else ""
        return err, names, "SECRET-CHANNEL" in body

    lib_link = run(link, "q-link")
    lib_parent = run(linked_parent / "channels.json", "q-parent")
    plain = tmp_path / "plain-channels.json"
    plain.write_text(outside.read_text(encoding="utf-8"), encoding="utf-8")
    plain_result = run(plain, "q-plain")

    cli_queue = tmp_path / "q-cli"
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "--channel-id", "chan-secret",
            "--topic", "cli-topic",
            "--queue-dir", str(cli_queue),
            "--config", str(link),
            "--workflows-config", str(workflows_path),
        ],
    )
    try:
        main()
        cli_err = None
    except ValueError as exc:
        cli_err = str(exc)
    cli_names = sorted(p.name for p in cli_queue.iterdir()) if cli_queue.exists() else []
    cli_body = (cli_queue / cli_names[0]).read_text(encoding="utf-8") if cli_names else ""
    assert (lib_link, lib_parent, plain_result[0], plain_result[2], cli_err, "SECRET-CHANNEL" in cli_body) == (
        ("refusing to follow a symlink", [], False),
        ("refusing to follow a symlink", [], False),
        None,
        True,
        "refusing to follow a symlink",
        False,
    )


def test_workflows_config_does_not_follow_a_symlink(tmp_path, fake_configs, monkeypatch):
    channels_path, _workflows, _queue = fake_configs
    outside = tmp_path / "outside-workflows.json"
    outside.write_text(json.dumps({
        "workflows": [{
            "workflow_id": "wf-test-1",
            "production_steps": ["SECRET-STEP"],
        }]
    }), encoding="utf-8")
    link = tmp_path / "linked-workflows.json"
    link.symlink_to(outside)

    parent_outside = tmp_path / "workflows-parent-outside"
    parent_outside.mkdir()
    (parent_outside / "workflows.json").write_text(outside.read_text(encoding="utf-8"), encoding="utf-8")
    linked_parent = tmp_path / "workflows-linked-parent"
    linked_parent.symlink_to(parent_outside, target_is_directory=True)

    def run(workflows, name):
        queue = tmp_path / name
        try:
            build_workflow_tasks_for_channel(
                "chan-test-1",
                "topic-x",
                queue_dir=queue,
                channels_path=channels_path,
                workflows_path=workflows,
            )
            err = None
        except ValueError as exc:
            err = str(exc)
        names = sorted(p.name for p in queue.iterdir()) if queue.exists() else []
        return err, names

    lib_link = run(link, "w-link")
    lib_parent = run(linked_parent / "workflows.json", "w-parent")
    plain = tmp_path / "plain-workflows.json"
    plain.write_text(outside.read_text(encoding="utf-8"), encoding="utf-8")
    plain_result = run(plain, "w-plain")

    cli_queue = tmp_path / "w-cli"
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "--channel-id", "chan-test-1",
            "--topic", "cli-topic",
            "--queue-dir", str(cli_queue),
            "--config", str(channels_path),
            "--workflows-config", str(link),
        ],
    )
    try:
        main()
        cli_err = None
    except ValueError as exc:
        cli_err = str(exc)
    cli_names = sorted(p.name for p in cli_queue.iterdir()) if cli_queue.exists() else []
    secret_name = "TASK-TEST-1-TOPIC-X-SECRET-STEP.json"
    cli_secret = "TASK-TEST-1-CLI-TOPIC-SECRET-STEP.json"
    assert (lib_link, lib_parent, plain_result, cli_err, cli_names) == (
        ("refusing to follow a symlink", []),
        ("refusing to follow a symlink", []),
        (None, [secret_name]),
        "refusing to follow a symlink",
        [],
    ) and cli_secret not in cli_names


def test_priority_must_be_an_int(fake_configs):
    channels_path, workflows_path, _queue = fake_configs

    def run(priority, name):
        try:
            tasks = build_workflow_tasks_for_channel(
                "chan-test-1",
                name,
                priority=priority,
                queue_dir=channels_path.parent / f"queue-{name}",
                channels_path=channels_path,
                workflows_path=workflows_path,
            )
        except ValueError as exc:
            return ("err", str(exc))
        return ("ok", tasks[0]["priority"])

    assert (run(True, "bool-true"), run(1.0, "float-one"), run(0, "int-zero")) == (
        ("err", "priority must be an int"),
        ("err", "priority must be an int"),
        ("ok", 0),
    )


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
