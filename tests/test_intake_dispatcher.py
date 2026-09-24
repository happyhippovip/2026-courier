import json
import os
import sys
import tempfile
import pytest

from scripts.intake_dispatcher import dispatch_intake, main


def test_dispatch_intake_validation_error():
    with tempfile.TemporaryDirectory() as tmp_dir:
        intake_file = os.path.join(tmp_dir, "bad_intake.json")
        with open(intake_file, "w", encoding="utf-8") as f:
            json.dump({"customer_reference": "cust-01"}, f)

        with pytest.raises(ValueError, match="Intake missing required fields"):
            dispatch_intake(intake_file, repo_dir=tmp_dir, dry_run=True)


def test_dispatch_intake_dry_run_success():
    with tempfile.TemporaryDirectory() as tmp_dir:
        intake_file = os.path.join(tmp_dir, "intake.json")
        state_file = os.path.join(tmp_dir, "central_state.json")

        intake_data = {
            "target_owner": "test-owner",
            "target_repo": "test-repo",
            "target_sha": "abc12345",
            "customer_reference": "ref-cust-99",
            "price_currency": "EUR_149",
        }
        with open(intake_file, "w", encoding="utf-8") as f:
            json.dump(intake_data, f)

        res = dispatch_intake(intake_file, repo_dir=tmp_dir, state_file=state_file, dry_run=True)
        assert res["status"] == "DISPATCHED"
        assert res["execution_ref"] == "DISPATCHED_DRY_RUN"

        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)

        task_id = res["task_id"]
        assert task_id in state["tasks"]
        assert state["tasks"][task_id]["customer_reference"] == "ref-cust-99"
        assert state["tasks"][task_id]["state"] == "DISPATCHED_TO_EXTERNAL"
