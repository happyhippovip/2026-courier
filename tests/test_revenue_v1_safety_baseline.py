from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import scripts.revenue_v1_safety_baseline as rsb


def test_hash_file(tmp_path: Path):
    f = tmp_path / "sample.txt"
    f.write_text("hello world\n", encoding="utf-8")
    h = rsb.hash_file(f)
    assert len(h) == 64
    assert h == rsb.hash_file(f)


def test_analyze_workflows_clean_and_violations(tmp_path: Path):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)

    # 1. Clean workflow
    clean_wf = wf_dir / "clean.yml"
    clean_wf.write_text(
        "name: CI\n"
        "on: [push]\n"
        "concurrency: group-1\n"
        "permissions:\n"
        "  contents: read\n"
        "jobs:\n"
        "  build:\n"
        "    runs-on: ubuntu-latest\n"
        "    timeout-minutes: 10\n"
        "    steps:\n"
        "      - run: echo ok\n",
        encoding="utf-8",
    )

    res = rsb.analyze_workflows(tmp_path)
    assert len(res["findings"]) == 0
    assert "clean.yml" in res["inspected_files"]

    # 2. Violations workflow
    bad_wf = wf_dir / "bad.yml"
    bad_wf.write_text(
        "name: Insecure\n"
        "jobs:\n"
        "  build:\n"
        "    runs-on: self-hosted\n"
        "    steps:\n"
        "      - run: git push origin main\n",
        encoding="utf-8",
    )

    res2 = rsb.analyze_workflows(tmp_path)
    rules = [f["rule"] for f in res2["findings"]]
    assert "runner_type" in rules
    assert "timeout" in rules
    assert "permissions" in rules
    assert "concurrency" in rules
    assert "mutation_risk" in rules


def test_worker_and_verify(tmp_path: Path):
    repo_dir = tmp_path / "mock_repo"
    wf_dir = repo_dir / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "ci.yml").write_text(
        "name: CI\npermissions:\n  contents: read\nconcurrency: c1\njobs:\n  t:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n",
        encoding="utf-8",
    )

    task = {
        "task_id": "task-001",
        "attempt_id": "att-001",
        "idempotency_key": "idem-001",
        "customer_reference": "cust-001",
        "target_owner": "test-owner",
        "target_repo": "test-repo",
        "target_sha": "abc1234",
    }

    work_dir = tmp_path / "worker_output"
    work_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(rsb, "clone_and_extract") as mock_clone:
        # Instead of cloning, copy mock_repo to destination
        def fake_clone(owner, repo, sha, dest):
            import shutil
            shutil.copytree(repo_dir, dest, dirs_exist_ok=True)

        mock_clone.side_effect = fake_clone
        result = rsb.worker(task, work_dir)

    assert result["worker_status"] == "PASS"
    assert result["effect_classification"] == "SAFE_READ_ONLY"
    assert (work_dir / "report.json").exists()
    assert (work_dir / "report.md").exists()

    # Test verify
    with patch.object(rsb, "clone_and_extract", side_effect=fake_clone):
        verified = rsb.verify(task, result, work_dir)
        assert verified["verifier_status"] == "PASS"
        assert verified["verifier_id"] == rsb.VERIFIER_ID

    # Test verify mismatch raises SystemExit
    tampered_result = dict(result)
    tampered_result["report_json_sha256"] = "tampered00000000000000000000000000000000000000000000000000000000"
    with patch.object(rsb, "clone_and_extract", side_effect=fake_clone):
        with pytest.raises(SystemExit, match="revenue workforce rejected"):
            rsb.verify(task, tampered_result, work_dir)


def test_reconcile_handoff(tmp_path: Path):
    task = {
        "task_id": "task-001",
        "attempt_id": "att-001",
        "idempotency_key": "idem-001",
        "customer_reference": "cust-001",
    }
    result = {
        "schema_version": "1.0",
        "task_id": "task-001",
        "attempt_id": "att-001",
        "idempotency_key": "idem-001",
        "github_run_id": "12345",
        "github_run_attempt": "1",
        "worker_result_id": "worker-att-001",
        "customer_reference": "cust-001",
        "report_json_sha256": "hash_json",
        "report_md_sha256": "hash_md",
        "effect_classification": "SAFE_READ_ONLY",
        "worker_status": "PASS",
        "proposal_mode": "PR_ONLY",
        "verifier_id": rsb.VERIFIER_ID,
        "verifier_status": "PASS",
        "next_safe_state": "HUMAN_REVIEW_REQUIRED",
    }
    commit_sha = "a" * 40
    handoff = {
        "task_id": "task-001",
        "attempt_id": "att-001",
        "result_path": "revenue_v1/results/task-001-att-001-12345-1.json",
        "verifier_id": rsb.VERIFIER_ID,
        "result_commit": commit_sha,
        "proposal_branch": "revenue/result-proposal-12345",
        "proposal_pr": "https://github.com/happyhippovip/2026-courier/pull/42",
        "human_merge_required": True,
    }

    with patch.object(rsb, "validate_verified_result"):
        reconciliation = rsb.reconcile_handoff(
            task=task,
            result=result,
            handoff=handoff,
            work_dir=tmp_path,
            proposal_number="42",
            proposal_head="revenue/result-proposal-12345",
            proposal_base="main",
        )
        assert reconciliation["status"] == "HANDOFF_RECONCILED"
        assert reconciliation["proposal_pr"] == "42"


def test_main_cli(tmp_path: Path, capsys):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps({
        "task_id": "t1",
        "attempt_id": "a1",
        "idempotency_key": "i1",
        "customer_reference": "c1",
        "target_owner": "o",
        "target_repo": "r",
        "target_sha": "s",
    }), encoding="utf-8")

    with patch.object(rsb, "worker", return_value={"status": "OK"}):
        code = rsb.main(["worker", str(task_file), str(tmp_path)])
        assert code == 0
        captured = capsys.readouterr()
        assert "OK" in captured.out
