import json
import os
import sys
import tempfile
import pytest

from scripts.revenue_customer_intake import submit_intake, main


def test_submit_intake_dry_run():
    with tempfile.TemporaryDirectory() as tmp_dir:
        res = submit_intake(
            owner="happyhippovip",
            repo="2026-courier",
            sha="abcdef123456",
            customer_ref="cust-corp-99",
            dry_run=True,
        )
        assert res["status"] == "DRY_RUN"
        assert res["goal_id"].startswith("REVENUE-GOAL-")
        assert res["task_id"].startswith("REV-")

        plan = res["payload"]["workflow_plan"]
        assert len(plan) == 1
        assert plan[0]["target_owner"] == "happyhippovip"
        assert plan[0]["target_repo"] == "2026-courier"
        assert plan[0]["customer_reference"] == "cust-corp-99"


def test_submit_intake_missing_api_key(monkeypatch):
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    monkeypatch.setattr("scripts.revenue_customer_intake.get_api_key", lambda rdir: None)

    with pytest.raises(RuntimeError, match="Missing COURIER_API_KEY"):
        submit_intake(
            owner="happyhippovip",
            repo="2026-courier",
            sha="abcdef123456",
            customer_ref="cust-corp-99",
            dry_run=False,
        )


def test_revenue_customer_intake_cli(capsys):
    orig_argv = sys.argv
    try:
        sys.argv = [
            "revenue_customer_intake.py",
            "test-owner", "test-repo", "12345678", "cust-ref-1",
            "--dry-run", "--json"
        ]
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "DRY_RUN"
    finally:
        sys.argv = orig_argv
