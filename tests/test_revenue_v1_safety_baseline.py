#!/usr/bin/env python3
"""Targeted unit tests for revenue_v1_safety_baseline validation and determinism."""

import pytest
from pathlib import Path
from scripts.revenue_v1_safety_baseline import clone_and_extract, analyze_workflows, verify, fail


def test_clone_and_extract_rejects_malformed_arguments(tmp_path: Path):
    dest = tmp_path / "dest"
    
    # Invalid owner
    with pytest.raises(SystemExit, match="Invalid owner format"):
        clone_and_extract("owner;curl", "repo", "0123456789abcdef", dest)
    with pytest.raises(SystemExit, match="Invalid owner format"):
        clone_and_extract("../../evil", "repo", "0123456789abcdef", dest)

    # Invalid repo
    with pytest.raises(SystemExit, match="Invalid repo format"):
        clone_and_extract("owner", "repo;rm", "0123456789abcdef", dest)
    with pytest.raises(SystemExit, match="Invalid repo format"):
        clone_and_extract("owner", "--upload-pack=evil", "0123456789abcdef", dest)

    # Invalid sha
    with pytest.raises(SystemExit, match="Invalid commit sha format"):
        clone_and_extract("owner", "repo", "--help", dest)
    with pytest.raises(SystemExit, match="Invalid commit sha format"):
        clone_and_extract("owner", "repo", "not_a_hex_sha!", dest)
    with pytest.raises(SystemExit, match="Invalid commit sha format"):
        clone_and_extract("owner", "repo", "123", dest)  # too short


def test_analyze_workflows_handles_yaml_and_yml_deterministically(tmp_path: Path):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)

    (wf_dir / "z_wf.yaml").write_text("name: Test\nruns-on: self-hosted\n", encoding="utf-8")
    (wf_dir / "a_wf.yml").write_text("name: Build\ngit push\n", encoding="utf-8")

    result = analyze_workflows(tmp_path)

    # Both yml and yaml files must be inspected
    assert "a_wf.yml" in result["inspected_files"]
    assert "z_wf.yaml" in result["inspected_files"]

    # Findings must be sorted deterministically
    findings = result["findings"]
    assert len(findings) >= 2
    # First finding must belong to a_wf.yml because sorted by file
    assert findings[0]["file"] == "a_wf.yml"
    assert any(f["rule"] == "runner_type" and f["file"] == "z_wf.yaml" for f in findings)
    assert any(f["rule"] == "mutation_risk" and f["file"] == "a_wf.yml" for f in findings)


def test_verify_rejects_hash_mismatch(monkeypatch, tmp_path: Path):
    task = {
        "target_owner": "testowner",
        "target_repo": "testrepo",
        "target_sha": "a" * 40,
        "task_id": "T-100",
        "attempt_id": "A-1",
        "idempotency_key": "IDEMP-1",
        "customer_reference": "REF-1"
    }
    
    # Mock worker
    fake_expected = {
        "report_json_sha256": "expected_hash_json",
        "report_md_sha256": "expected_hash_md"
    }
    monkeypatch.setattr("scripts.revenue_v1_safety_baseline.worker", lambda t, d: fake_expected)

    candidate = {
        "task_id": "T-100",
        "report_json_sha256": "mismatched_hash_json"
    }

    with pytest.raises(SystemExit, match="Verification failed"):
        verify(task, candidate, tmp_path)
