import pytest
import json
import os
from pathlib import Path
from scripts.revenue_v1_safety_baseline import analyze_workflows, hash_file

def test_analyze_workflows_safe(tmp_path):
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    
    wf = workflows_dir / "safe.yml"
    wf.write_text("""
name: Safe Workflow
on: push
permissions:
  contents: read
concurrency:
  group: safe
jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - run: echo 'safe'
    """)
    
    analysis = analyze_workflows(tmp_path)
    
    assert "safe.yml" in analysis["inspected_files"]
    assert len(analysis["findings"]) == 0

def test_analyze_workflows_violations(tmp_path):
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    
    wf = workflows_dir / "unsafe.yml"
    wf.write_text("""
name: Unsafe Workflow
on: push
# missing permissions
# missing concurrency
jobs:
  build:
    runs-on: self-hosted
    # missing timeout-minutes
    steps:
      - run: git push origin main
    """)
    
    analysis = analyze_workflows(tmp_path)
    
    assert "unsafe.yml" in analysis["inspected_files"]
    
    findings = analysis["findings"]
    assert len(findings) == 5
    rules_violated = {f["rule"] for f in findings}
    
    assert "runner_type" in rules_violated
    assert "timeout" in rules_violated
    assert "permissions" in rules_violated
    assert "concurrency" in rules_violated
    assert "mutation_risk" in rules_violated

def test_analyze_workflows_write_all(tmp_path):
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    
    wf = workflows_dir / "write_all.yml"
    wf.write_text("""
name: Write All Workflow
on: push
permissions: write-all
concurrency:
  group: write
jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - run: echo 'write'
    """)
    
    analysis = analyze_workflows(tmp_path)
    findings = analysis["findings"]
    assert len(findings) == 1
    assert findings[0]["rule"] == "permissions"
    assert "write-all" in findings[0]["issue"]

def test_hash_file(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"hello world")
    
    import hashlib
    expected = hashlib.sha256(b"hello world").hexdigest()
    
    assert hash_file(test_file) == expected

