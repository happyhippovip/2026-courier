import pytest
import os
import sys
import json
import shutil
from unittest import mock
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import revenue_v1_safety_baseline

def test_hash_file(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("hello")
    # echo -n hello | shasum -a 256
    assert revenue_v1_safety_baseline.hash_file(f) == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

def test_clone_and_extract(tmp_path):
    dest = tmp_path / "repo"
    
    with mock.patch("subprocess.run") as mock_run:
        revenue_v1_safety_baseline.clone_and_extract("owner", "repo", "sha123", dest)
        assert mock_run.call_count == 2
        
        args1 = mock_run.call_args_list[0][0][0]
        assert "clone" in args1
        assert "https://github.com/owner/repo.git" in args1
        
        args2 = mock_run.call_args_list[1][0][0]
        assert "checkout" in args2
        assert "sha123" in args2

def test_analyze_workflows(tmp_path):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    
    wf1 = wf_dir / "wf1.yml"
    wf1.write_text("runs-on: self-hosted\nwrite-all\n")
    
    wf2 = wf_dir / "wf2.yml"
    wf2.write_text("timeout-minutes: 10\npermissions: read-all\nconcurrency: group1\n")
    
    analysis = revenue_v1_safety_baseline.analyze_workflows(tmp_path)
    
    assert "wf1.yml" in analysis["inspected_files"]
    assert "wf2.yml" in analysis["inspected_files"]
    
    findings = analysis["findings"]
    rules_violated = {f["rule"] for f in findings if f["file"] == "wf1.yml"}
    
    assert "runner_type" in rules_violated
    assert "timeout" in rules_violated
    assert "permissions" in rules_violated
    assert "concurrency" in rules_violated
    
    rules_violated_2 = {f["rule"] for f in findings if f["file"] == "wf2.yml"}
    assert len(rules_violated_2) == 0

@mock.patch("scripts.revenue_v1_safety_baseline.clone_and_extract")
@mock.patch("scripts.revenue_v1_safety_baseline.analyze_workflows")
def test_worker(mock_analyze, mock_clone, tmp_path):
    mock_analyze.return_value = {"inspected_files": {}, "findings": []}
    
    task = {
        "task_id": "t1",
        "attempt_id": "a1",
        "idempotency_key": "k1",
        "customer_reference": "ref",
        "target_owner": "owner",
        "target_repo": "repo",
        "target_sha": "sha"
    }
    
    res = revenue_v1_safety_baseline.worker(task, tmp_path)
    
    mock_clone.assert_called_once()
    
    # Check that report JSON and MD are written
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "report.md").exists()
    
    assert res["task_id"] == "t1"
    assert res["worker_status"] == "PASS"

@mock.patch("scripts.revenue_v1_safety_baseline.worker")
def test_verify(mock_worker, tmp_path):
    mock_worker.return_value = {
        "report_json_sha256": "hash_json",
        "report_md_sha256": "hash_md"
    }
    
    candidate = {
        "report_json_sha256": "hash_json",
        "report_md_sha256": "hash_md",
        "other": "data"
    }
    
    res = revenue_v1_safety_baseline.verify({}, candidate, tmp_path)
    
    assert res["verifier_id"] == "revenue-v1-independent-verifier"
    assert res["verifier_status"] == "PASS"
    assert res["next_safe_state"] == "HUMAN_REVIEW_REQUIRED"
    assert res["other"] == "data"
    
    # Check mismatch
    candidate["report_json_sha256"] = "wrong_hash"
    with pytest.raises(SystemExit) as exc:
        revenue_v1_safety_baseline.verify({}, candidate, tmp_path)
    assert "hashes do not match" in str(exc.value)

@mock.patch("scripts.revenue_v1_safety_baseline.verify")
def test_reconcile_handoff(mock_verify, tmp_path):
    task = {}
    result = {
        "github_run_id": "run1",
        "github_run_attempt": "1",
        "task_id": "t1",
        "attempt_id": "a1",
        "idempotency_key": "k1",
        "worker_result_id": "w1"
    }
    handoff = {
        "task_id": "t1",
        "attempt_id": "a1",
        "result_path": "revenue_v1/results/t1-a1-run1-1.json",
        "verifier_id": "revenue-v1-independent-verifier",
        "result_commit": "0" * 40,
        "proposal_branch": "revenue/result-proposal-123",
        "proposal_pr": "https://github.com/happyhippovip/2026-courier/pull/456",
        "human_merge_required": True
    }
    
    mock_verify.return_value = result # So it passes validation
    
    recon = revenue_v1_safety_baseline.reconcile_handoff(
        task, result, handoff, tmp_path, "456", "revenue/result-proposal-123", "main"
    )
    
    assert recon["status"] == "HANDOFF_RECONCILED"
    assert recon["proposal_pr"] == "456"

