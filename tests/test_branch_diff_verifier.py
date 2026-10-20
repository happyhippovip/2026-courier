from __future__ import annotations
import os

import json
import subprocess
import sys
from pathlib import Path

import pytest

from courier_core.branch_diff_verifier import (
    verify_changed_files_scope,
    BranchDiffReport,
)


def test_verify_branch_diff_within_scope():
    changed = ["courier_core/new_feature.py", "tests/test_new_feature.py"]
    scope = ["courier_core/*", "tests/*"]
    report = verify_changed_files_scope(changed, allowed_scope=scope)

    assert isinstance(report, BranchDiffReport)
    assert report.valid is True
    assert len(report.out_of_scope) == 0
    assert len(report.protected_breaches) == 0
    assert report.changed_files == changed


def test_verify_branch_diff_detects_out_of_scope():
    changed = ["courier_core/feature.py", "server/unauthorized.py"]
    scope = ["courier_core/*"]
    report = verify_changed_files_scope(changed, allowed_scope=scope)

    assert report.valid is False
    assert "server/unauthorized.py" in report.out_of_scope
    assert "courier_core/feature.py" not in report.out_of_scope


def test_verify_branch_diff_blocks_protected_baseline():
    changed = ["courier_core/feature.py", "courier_v3/core.py"]
    scope = ["courier_core/*", "courier_v3/*"]
    protected = ["courier_v3/**", "contracts/v3/**"]

    report = verify_changed_files_scope(changed, allowed_scope=scope, protected_patterns=protected)
    assert report.valid is False
    assert "courier_v3/core.py" in report.protected_breaches

    # Path traversal trying to escape allowed_dir/** into courier_v3/** must be blocked
    traversal = verify_changed_files_scope(
        ["courier_core/../../courier_v3/core.py"],
        allowed_scope=["courier_core/**"],
        protected_patterns=protected,
    )
    assert traversal.valid is False
    assert "courier_core/../../courier_v3/core.py" in traversal.protected_breaches


def test_pattern_matching_glob_and_subdirectories():
    changed = ["src/nested/sub/module.py", "docs/index.md"]
    scope = ["src/**", "docs/*.md"]
    report = verify_changed_files_scope(changed, allowed_scope=scope)
    assert report.valid is True


def test_empty_scope_blocks_all():
    changed = ["any_file.py"]
    report = verify_changed_files_scope(changed, allowed_scope=[])
    assert report.valid is False
    assert "any_file.py" in report.out_of_scope


def test_cli_invocation_happy_and_breach(tmp_path: Path):
    manifest = tmp_path / "diff_manifest.json"
    manifest.write_text(json.dumps({
        "changed": ["courier_core/mod.py", "tests/test_mod.py"],
        "scope": ["courier_core/*", "tests/*"],
        "protected": ["v3/*"],
    }), encoding="utf-8")

    root = str(Path(__file__).resolve().parent.parent)
    env = os.environ.copy()
    env["PYTHONPATH"] = root

    res = subprocess.run(
        [sys.executable, "-m", "courier_core.branch_diff_verifier", str(manifest)],
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["valid"] is True

    # Breach manifest
    manifest_bad = tmp_path / "bad.json"
    manifest_bad.write_text(json.dumps({
        "changed": ["v3/protected.py"],
        "scope": ["*"],
        "protected": ["v3/*"],
    }), encoding="utf-8")

    res_bad = subprocess.run(
        [sys.executable, "-m", "courier_core.branch_diff_verifier", str(manifest_bad)],
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
    )
    assert res_bad.returncode == 1
    data_bad = json.loads(res_bad.stdout)
    assert data_bad["valid"] is False
    assert "v3/protected.py" in data_bad["protected_breaches"]
