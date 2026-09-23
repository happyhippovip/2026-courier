import json
import pytest
from pathlib import Path

from scripts.intake_dispatcher import (
    validate_intake_data,
    dispatch_intake,
    get_canonical_state_path,
    load_state_safe,
    atomic_save_json,
)
from scripts.queue_processor import process_queue


def test_validate_intake_data_valid():
    valid = {
        "target_owner": "happyhippovip",
        "target_repo": "2026-courier",
        "target_sha": "a" * 40,
        "customer_reference": "cust-ref-1234",
    }
    # Should not raise
    validate_intake_data(valid)


@pytest.mark.parametrize(
    "field,value",
    [
        ("target_owner", "invalid owner with spaces"),
        ("target_owner", ""),
        ("target_repo", "bad/slash/repo"),
        ("target_sha", "short"),
        ("target_sha", "g" * 40),  # non-hex
        ("customer_reference", ""),
        ("customer_reference", "has\x00null"),
    ],
)
def test_validate_intake_data_invalid(field, value):
    data = {
        "target_owner": "owner",
        "target_repo": "repo",
        "target_sha": "a" * 40,
        "customer_reference": "ref",
    }
    data[field] = value
    with pytest.raises(ValueError):
        validate_intake_data(data)


def test_dispatch_intake_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        dispatch_intake(tmp_path / "nonexistent.json")


def test_dispatch_intake_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ unclosed", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        dispatch_intake(bad)


def test_dispatch_intake_success_with_mock_runner(tmp_path):
    intake_file = tmp_path / "intake.json"
    state_file = tmp_path / "central_state.json"

    intake_data = {
        "target_owner": "happyhippovip",
        "target_repo": "2026-courier",
        "target_sha": "f" * 40,
        "customer_reference": "customer-abc",
    }
    intake_file.write_text(json.dumps(intake_data), encoding="utf-8")

    captured_cmds = []

    def mock_gh(cmd):
        captured_cmds.append(cmd)
        return "GH-RUN-999"

    res = dispatch_intake(intake_file, state_file=str(state_file), gh_runner=mock_gh)
    assert res["ok"] is True
    assert res["execution_ref"] == "GH-RUN-999"
    assert res["customer_reference"] == "customer-abc"
    assert len(captured_cmds) == 1

    # Verify central state was updated
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert res["task_id"] in state["tasks"]
    task_entry = state["tasks"][res["task_id"]]
    assert task_entry["customer_reference"] == "customer-abc"
    assert task_entry["execution_ref"] == "GH-RUN-999"
    assert task_entry["state"] == "DISPATCHED_TO_EXTERNAL"


def test_dispatch_intake_corrupt_state_recovery(tmp_path):
    intake_file = tmp_path / "intake.json"
    state_file = tmp_path / "central_state.json"

    intake_data = {
        "target_owner": "happyhippovip",
        "target_repo": "2026-courier",
        "target_sha": "f" * 40,
        "customer_reference": "customer-corrupt-test",
    }
    intake_file.write_text(json.dumps(intake_data), encoding="utf-8")
    state_file.write_text("{ corrupt json ...", encoding="utf-8")

    res = dispatch_intake(intake_file, state_file=str(state_file), gh_runner=lambda cmd: "RUN-1")
    assert res["ok"] is True

    # Corrupt file should be quarantined
    corrupt_backups = list(tmp_path.glob("central_state.json.corrupt.*"))
    assert len(corrupt_backups) == 1

    # New state is valid
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert res["task_id"] in state["tasks"]


def test_dispatch_intake_failure_keeps_state_untouched(tmp_path):
    intake_file = tmp_path / "intake.json"
    state_file = tmp_path / "central_state.json"
    state_file.write_text(json.dumps({"tasks": {"existing": 1}}), encoding="utf-8")

    intake_data = {
        "target_owner": "happyhippovip",
        "target_repo": "2026-courier",
        "target_sha": "f" * 40,
        "customer_reference": "fail-ref",
    }
    intake_file.write_text(json.dumps(intake_data), encoding="utf-8")

    def failing_gh(cmd):
        raise RuntimeError("Workflow not found")

    with pytest.raises(RuntimeError):
        dispatch_intake(intake_file, state_file=str(state_file), gh_runner=failing_gh)

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state == {"tasks": {"existing": 1}}


def test_queue_processor_end_to_end(tmp_path):
    pending = tmp_path / "pending"
    processed = tmp_path / "processed"
    failed = tmp_path / "failed"
    state_file = tmp_path / "state.json"

    # Valid intake
    valid_file = pending / "valid.json"
    pending.mkdir(parents=True)
    valid_file.write_text(
        json.dumps({
            "target_owner": "user",
            "target_repo": "repo",
            "target_sha": "e" * 40,
            "customer_reference": "ref-ok",
        }),
        encoding="utf-8",
    )

    # Invalid intake (poison pill)
    invalid_file = pending / "invalid.json"
    invalid_file.write_text(
        json.dumps({
            "target_owner": "bad owner with spaces",
            "target_repo": "repo",
            "target_sha": "short",
            "customer_reference": "ref-bad",
        }),
        encoding="utf-8",
    )

    summary = process_queue(
        pending_dir=pending,
        processed_dir=processed,
        failed_dir=failed,
        state_file=str(state_file),
        gh_runner=lambda cmd: "RUN-MOCK",
    )

    assert summary["total_scanned"] == 2
    assert summary["processed"] == 1
    assert summary["failed"] == 1

    # Valid moved to processed
    assert not valid_file.exists()
    assert (processed / "valid.json").exists()

    # Invalid moved to failed with error file
    assert not invalid_file.exists()
    assert (failed / "invalid.json").exists()
    assert (failed / "invalid.error.json").exists()

    # Central state has the valid task
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(state["tasks"]) == 1
