"""Deterministic and isolated tests for Paths with Spaces (SEED 155).

Verifies authentic handling, execution, artifact generation, SHA256 evidence,
and boundary confinement in Windows directories and files with spaces.
"""
import os
from pathlib import Path
import subprocess
import sys
import pytest

from courier_runtime.workspace import (
    Workspace,
    Step,
    resolve_workspace_child,
    find_authentic_workspace_root,
    verify_workspace_root,
    verify_verbatim_path,
    to_verbatim_path,
    normalize_path,
)
from courier_runtime.continuation import AcceptedLog
from courier_runtime.grants import Broker, Request
from courier_runtime.hosts import Host, Requirement
from courier_runtime.lease import LeaseStore
from courier_runtime.ownership import Registry


class MockClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def create_spaced_world(workdir_path):
    clock = MockClock()
    hosts = [Host("win-1", frozenset({"python", "windows_native"}), privacy="own")]
    broker = Broker(clock)
    req = Request("r1", "p1", "fs.write", frozenset({"workspace:p1"}), "any", "", "project", "write", "idempotent")
    broker.authorize(req)
    broker.grant(req, "g1", expires_at=None)

    workdir_path.mkdir(parents=True, exist_ok=True)
    lease_path = workdir_path / "lease.db"
    leases = LeaseStore(str(lease_path), clock=clock)
    accepted_log = AcceptedLog(str(workdir_path / "accepted.jsonl"))
    registry = Registry(str(workdir_path / "owned.json"))

    ws = Workspace(
        hosts=hosts,
        lease_store=leases,
        broker=broker,
        accepted_log=accepted_log,
        registry=registry,
        workdir=str(workdir_path),
        clock=clock,
        lease_ttl_s=30,
    )
    return ws, hosts, req, leases


def test_positive_workspace_execution_in_dir_with_spaces(tmp_path):
    """Real child process execution and artifact evidence in a workdir with spaces."""
    spaced_dir = tmp_path / "My Courier Workspace 2026"
    ws, hosts, req, leases = create_spaced_world(spaced_dir)

    code = (
        "import pathlib; "
        "pathlib.Path('final report 2026.txt').write_bytes(b'execution_with_spaces_ok')"
    )
    step = Step("step_spaced", [sys.executable, "-c", code], "final report 2026.txt")

    try:
        result = ws.run("wk-spaces", Requirement(frozenset({"python"})), "project:p1", req, [step], host=hosts[0])
        assert result["state"] == "DONE"
        assert result["steps"] == 1

        out_file = spaced_dir / "final report 2026.txt"
        assert out_file.exists()
        assert out_file.read_bytes() == b"execution_with_spaces_ok"

        facts = ws.log.facts("wk-spaces")
        assert len(facts) == 1
        assert "final report 2026.txt" in facts[0].statement
        assert facts[0].sources[0].startswith("evidence:")
    finally:
        leases.close()


def test_positive_subdirectories_with_spaces(tmp_path):
    """Nested subdirectories with multiple spaces in folder and file names."""
    spaced_dir = tmp_path / "Workspace Root"
    sub_dir = spaced_dir / "reports folder" / "run 01"
    sub_dir.mkdir(parents=True, exist_ok=True)
    ws, hosts, req, leases = create_spaced_world(spaced_dir)

    code = (
        "import pathlib; "
        "pathlib.Path('reports folder/run 01/deep output file.json').write_bytes(b'{\"spaced\": true}')"
    )
    step = Step("step_deep", [sys.executable, "-c", code], "reports folder/run 01/deep output file.json")

    try:
        result = ws.run("wk-deep", Requirement(frozenset({"python"})), "project:p1", req, [step], host=hosts[0])
        assert result["state"] == "DONE"

        out_file = spaced_dir / "reports folder" / "run 01" / "deep output file.json"
        assert out_file.exists()
        assert b"\"spaced\": true" in out_file.read_bytes()
    finally:
        leases.close()


def test_positive_verbatim_path_with_spaces(tmp_path):
    """Windows verbatim path (\\\\?\\) with spaces is verified and normalized cleanly."""
    target_dir = tmp_path / "Program Files" / "Courier Data Store"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "database file.db"
    target_file.write_bytes(b"data")

    verbatim = f"\\\\?\\{str(target_file)}"
    valid, result = verify_verbatim_path(verbatim, must_exist=True)
    assert valid is True
    assert "Program Files" in result
    assert "Courier Data Store" in result


def test_positive_authentic_root_discovery_with_spaces(tmp_path):
    """Authentic root discovery traverses through directories with spaces."""
    repo_root = tmp_path / "Company Project Workspace"
    leaf = repo_root / "sub package folder" / "module dir"
    leaf.mkdir(parents=True)
    (repo_root / ".git").mkdir()
    (repo_root / "pyproject.toml").touch()

    discovered = find_authentic_workspace_root(start_path=leaf)
    assert discovered == repo_root.resolve()

    valid, details = verify_workspace_root(leaf, expected_name="Company Project Workspace")
    assert valid is True
    assert details == str(repo_root.resolve())


def test_negative_path_escaping_workspace_with_spaces(tmp_path):
    """Boundary confinement prevents breakout from a workspace with spaces."""
    spaced_dir = tmp_path / "Main Workspace"
    ws, hosts, req, leases = create_spaced_world(spaced_dir)

    # 1. Traversal relative
    assert resolve_workspace_child(spaced_dir, "../outside spaced file.txt") is None

    # 2. Sibling directory with shared prefix and space
    sibling = str(spaced_dir) + " Malicious"
    assert resolve_workspace_child(spaced_dir, f"{sibling}/file.txt") is None

    # 3. Workspace execution fails closed when step attempts to escape
    escaping_step = Step("malicious", [sys.executable, "-c", "pass"], "../escaped space.txt")
    try:
        result = ws.run("wk-escape", Requirement(frozenset({"python"})), "project:p1", req, [escaping_step], host=hosts[0])
        assert result["state"] == "FAILED"
        assert any("escapes workdir" in r for r in result["reasons"])
    finally:
        leases.close()


def test_cli_verify_workspace_root_with_spaces_subprocess(tmp_path):
    """CLI subprocess validates authentic root when paths contain spaces."""
    py = sys.executable
    script = os.path.join("scripts", "verify_workspace_root.py")

    repo_root = tmp_path / "My Courier App 2026"
    deep = repo_root / "nested sub dir" / "leaf"
    deep.mkdir(parents=True)
    (repo_root / "pyproject.toml").touch()

    proc = subprocess.run([py, script, "--path", str(deep), "--expected-name", "My Courier App 2026"], capture_output=True, text=True)
    assert proc.returncode == 0
    assert "AUTHENTIC WORKSPACE ROOT: " in proc.stdout
    assert "My Courier App 2026" in proc.stdout


def test_cli_verify_verbatim_path_with_spaces_subprocess(tmp_path):
    """CLI subprocess validates verbatim paths with spaces."""
    py = sys.executable
    script = os.path.join("scripts", "verify_verbatim_path.py")

    spaced_dir = tmp_path / "Folder With Spaces"
    spaced_dir.mkdir(parents=True)
    spaced_file = spaced_dir / "target file.txt"
    spaced_file.write_text("ok")

    verbatim_path = f"\\\\?\\{str(spaced_file)}"
    proc = subprocess.run([py, script, verbatim_path, "--must-exist"], capture_output=True, text=True)
    assert proc.returncode == 0
    assert "VERBATIM PATH VALID: " in proc.stdout
    assert "target file.txt" in proc.stdout
