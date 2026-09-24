import json
import pytest
from pathlib import Path

from scripts.queue_processor import process_queue, main


@pytest.fixture
def mock_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "test_repo"
    repo.mkdir()
    (repo / "intakes" / "pending").mkdir(parents=True)
    (repo / "intakes" / "processed").mkdir(parents=True)
    (repo / "intakes" / "failed").mkdir(parents=True)
    return repo


def test_process_queue_empty(mock_repo: Path):
    results = process_queue(repo_dir=mock_repo, dry_run=True)
    assert results == []


def test_process_queue_success(mock_repo: Path):
    intake_data = {
        "target_owner": "test-owner",
        "target_repo": "test-repo",
        "target_sha": "abc12345",
        "customer_reference": "cust-ref-001",
        "price_currency": "EUR_99",
        "delivery_destination": "none"
    }
    intake_file = mock_repo / "intakes" / "pending" / "intake_001.json"
    intake_file.write_text(json.dumps(intake_data), encoding="utf-8")

    results = process_queue(repo_dir=mock_repo, dry_run=True)
    assert len(results) == 1
    assert results[0]["file"] == "intake_001.json"
    assert results[0]["status"] == "PROCESSED"

    # Verify intake moved from pending to processed
    assert not intake_file.exists()
    processed_file = mock_repo / "intakes" / "processed" / "intake_001.json"
    assert processed_file.is_file()

    # Central state was updated
    central_state = mock_repo / "central_state.json"
    assert central_state.is_file()
    state_data = json.loads(central_state.read_text(encoding="utf-8"))
    assert len(state_data.get("tasks", {})) == 1


def test_process_queue_destination_already_exists(mock_repo: Path):
    # Pre-create file in processed
    processed_file = mock_repo / "intakes" / "processed" / "intake_dup.json"
    processed_file.write_text(json.dumps({"old": "data"}), encoding="utf-8")

    intake_data = {
        "target_owner": "test-owner",
        "target_repo": "test-repo",
        "target_sha": "abc12345",
        "customer_reference": "cust-ref-dup",
    }
    pending_file = mock_repo / "intakes" / "pending" / "intake_dup.json"
    pending_file.write_text(json.dumps(intake_data), encoding="utf-8")

    # Should safely overwrite without FileExistsError
    results = process_queue(repo_dir=mock_repo, dry_run=True)
    assert len(results) == 1
    assert results[0]["status"] == "PROCESSED"
    assert not pending_file.exists()
    assert processed_file.is_file()


def test_process_queue_invalid_intake_fails(mock_repo: Path):
    # Missing required target_owner, target_repo, etc.
    invalid_data = {"customer_reference": "broken-intake"}
    pending_file = mock_repo / "intakes" / "pending" / "broken.json"
    pending_file.write_text(json.dumps(invalid_data), encoding="utf-8")

    results = process_queue(repo_dir=mock_repo, dry_run=True)
    assert len(results) == 1
    assert results[0]["status"] == "FAILED"
    assert "Intake missing required fields" in results[0]["error"]

    # File moved to failed directory
    assert not pending_file.exists()
    failed_file = mock_repo / "intakes" / "failed" / "broken.json"
    assert failed_file.is_file()


def test_queue_processor_cli(mock_repo: Path, capsys):
    intake_data = {
        "target_owner": "test-owner",
        "target_repo": "test-repo",
        "target_sha": "abc12345",
        "customer_reference": "cust-ref-cli",
    }
    pending_file = mock_repo / "intakes" / "pending" / "cli_intake.json"
    pending_file.write_text(json.dumps(intake_data), encoding="utf-8")

    code = main([
        "--repo-dir", str(mock_repo),
        "--dry-run",
        "--json"
    ])
    assert code == 0
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert len(res) == 1
    assert res[0]["status"] == "PROCESSED"
