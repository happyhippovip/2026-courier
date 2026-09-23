import json
import os
from pathlib import Path
import tempfile
import zipfile
import pytest

from scripts.support_bundle import (
    get_system_health,
    generate_redacted_queue_summary,
    create_support_bundle,
)


def test_system_health():
    health = get_system_health()
    assert "os" in health
    assert "platform" in health
    assert "python_version" in health
    assert "timestamp_utc" in health
    assert "disk_free_gb" in health


def test_generate_redacted_queue_summary():
    with tempfile.TemporaryDirectory() as td:
        state_file = Path(td) / "central_state.json"
        state = {
            "goals": {
                "g1": {
                    "workflow_plan": [
                        {"task_id": "t1", "status": "RUNNING", "secret_key": "MUST_NOT_LEAK"},
                        {"task_id": "t2", "status": "DONE"},
                    ]
                },
                "g2": {
                    "workflow_plan": [
                        {"task_id": "t3", "status": "WAITING"},
                    ]
                }
            },
            "schema_version": "1.0.0",
            "super_secret_auth": "courier-admin-token"
        }
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f)

        summary = generate_redacted_queue_summary(state_file)
        assert summary["status"] == "available"
        assert summary["total_goals"] == 2
        assert summary["total_workflow_tasks"] == 3
        assert summary["status_counts"]["RUNNING"] == 1
        assert summary["status_counts"]["DONE"] == 1
        assert summary["status_counts"]["WAITING"] == 1

        # Redaction verification: neither super_secret_auth nor task secret_key in summary
        summary_str = json.dumps(summary)
        assert "MUST_NOT_LEAK" not in summary_str
        assert "courier-admin-token" not in summary_str


def test_generate_queue_summary_missing_or_corrupt_state():
    with tempfile.TemporaryDirectory() as td:
        missing_file = Path(td) / "missing.json"
        summary = generate_redacted_queue_summary(missing_file)
        assert summary["status"] == "state_file_not_found"

        corrupt_file = Path(td) / "corrupt.json"
        with open(corrupt_file, "w", encoding="utf-8") as f:
            f.write("{invalid json")
        corrupt_summary = generate_redacted_queue_summary(corrupt_file)
        assert corrupt_summary["status"] == "unparseable"


def test_create_support_bundle():
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        state_file = tdp / "central_state.json"
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"goals": {}, "schema_version": "1.0.0"}, f)

        bundle_path = create_support_bundle(
            state_file=str(state_file),
            output_dir=str(tdp),
        )
        assert bundle_path.exists()
        assert bundle_path.suffix == ".zip"

        # Verify zip contents
        with zipfile.ZipFile(bundle_path, "r") as zf:
            namelist = zf.namelist()
            assert "health.json" in namelist
            assert "queue_summary.json" in namelist
            assert "version.txt" in namelist

            health_content = json.loads(zf.read("health.json").decode("utf-8"))
            assert "os" in health_content

            queue_content = json.loads(zf.read("queue_summary.json").decode("utf-8"))
            assert queue_content["status"] == "available"
