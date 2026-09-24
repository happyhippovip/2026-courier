import json
import pytest
from pathlib import Path

from scripts.run_batch import (
    get_next_item,
    load_batch,
    save_batch,
    run_batch,
    main,
)


@pytest.fixture
def queue_dir(tmp_path: Path) -> Path:
    q = tmp_path / "queue"
    q.mkdir(parents=True)
    return q


def test_load_and_save_batch_utf8(tmp_path: Path):
    batch_file = tmp_path / "test_utf8_batch.json"
    data = {
        "batch_id": "b-utf8",
        "description": "Unicode test: äöü ß € — 🚀",
        "items": [
            {"sequence": 1, "status": "QUEUED", "description": "Step 1"}
        ]
    }
    save_batch(batch_file, data)
    assert batch_file.is_file()

    loaded = load_batch(batch_file)
    assert loaded["description"] == data["description"]
    assert loaded["items"][0]["description"] == "Step 1"


def test_get_next_item():
    batch = {
        "items": [
            {"sequence": 2, "status": "QUEUED", "depends_on": 1},
            {"sequence": 1, "status": "QUEUED", "depends_on": None},
        ]
    }
    # Item 1 has no dependency, so it goes first
    item = get_next_item(batch)
    assert item["sequence"] == 1

    # While item 1 is IN_PROGRESS, it has top priority
    batch["items"][1]["status"] = "IN_PROGRESS"
    assert get_next_item(batch)["sequence"] == 1

    # Once item 1 is COMPLETED, item 2 can run
    batch["items"][1]["status"] = "COMPLETED"
    assert get_next_item(batch)["sequence"] == 2


def test_run_batch_execution(queue_dir: Path):
    batch_id = "batch-test-001"
    batch_file = queue_dir / f"{batch_id}.json"
    data = {
        "batch_id": batch_id,
        "items": [
            {
                "sequence": 1,
                "goal_id": "goal-1",
                "prompt_id": "prompt-1",
                "status": "QUEUED",
                "depends_on": None,
                "description": "First step"
            },
            {
                "sequence": 2,
                "goal_id": "goal-2",
                "prompt_id": "prompt-2",
                "status": "QUEUED",
                "depends_on": 1,
                "description": "Second step"
            }
        ]
    }
    save_batch(batch_file, data)

    res = run_batch(batch_id, queue_dir=queue_dir, fast=True)
    assert res is not None
    assert res["last_completed"] == 2
    assert res["dirty_worktree"] is False

    for item in res["items"]:
        assert item["status"] == "COMPLETED"
        assert item["evidence"]["verifier_acceptance"] == "PASS"
        assert "commit_sha" in item["evidence"]


def test_run_batch_with_quota_hit(queue_dir: Path):
    batch_id = "batch-quota-001"
    batch_file = queue_dir / f"{batch_id}.json"
    data = {
        "batch_id": batch_id,
        "items": [
            {
                "sequence": 9,
                "goal_id": "goal-quota",
                "prompt_id": "prompt-quota",
                "status": "QUEUED",
                "depends_on": None,
                "description": "Quota test step"
            }
        ]
    }
    save_batch(batch_file, data)

    res = run_batch(batch_id, queue_dir=queue_dir, fast=True)
    assert res is not None
    item = res["items"][0]
    assert item["status"] == "COMPLETED"
    assert item["quota_hit_simulated"] is True


def test_run_batch_main_cli(queue_dir: Path, capsys):
    batch_id = "batch-cli-001"
    batch_file = queue_dir / f"{batch_id}.json"
    data = {
        "batch_id": batch_id,
        "items": [
            {
                "sequence": 1,
                "goal_id": "goal-cli",
                "prompt_id": "prompt-cli",
                "status": "QUEUED",
                "depends_on": None,
                "description": "CLI step"
            }
        ]
    }
    save_batch(batch_file, data)

    # Missing batch
    code_missing = main(["non-existent", "--queue-dir", str(queue_dir), "--json"])
    assert code_missing == 1
    capsys.readouterr()

    # Successful run
    code_success = main([batch_id, "--queue-dir", str(queue_dir), "--fast", "--json"])
    assert code_success == 0
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["status"] == "COMPLETED"
    assert res["last_completed"] == 1
