"""Deterministic and isolated tests for Unicode Workspaces (SEED 154).

Verifies authentic handling, execution, artifact generation, SHA256 evidence,
and boundary confinement in Windows Unicode directories (German Umlaute, CJK, accents, verbatim).
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


def create_unicode_world(workdir_path):
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


def test_positive_workspace_execution_in_german_umlaut_dir(tmp_path):
    """Real child process execution and artifact evidence in a German Umlaut workdir."""
    u_dir = tmp_path / "München_Prüfung_2026"
    ws, hosts, req, leases = create_unicode_world(u_dir)

    code = (
        "import pathlib; "
        "pathlib.Path('ergebnis_äöü_ß.out').write_bytes(b'erfolgreich_ausgefuehrt')"
    )
    step = Step("schritt_1", [sys.executable, "-c", code], "ergebnis_äöü_ß.out")

    try:
        result = ws.run("wk-umlaut", Requirement(frozenset({"python"})), "project:p1", req, [step], host=hosts[0])
        assert result["state"] == "DONE"
        assert result["steps"] == 1

        out_file = u_dir / "ergebnis_äöü_ß.out"
        assert out_file.exists()
        assert out_file.read_bytes() == b"erfolgreich_ausgefuehrt"

        facts = ws.log.facts("wk-umlaut")
        assert len(facts) == 1
        assert "ergebnis_äöü_ß.out" in facts[0].statement
        assert facts[0].sources[0].startswith("evidence:")
    finally:
        leases.close()


def test_positive_workspace_execution_in_cjk_dir(tmp_path):
    """Real process execution and evidence collection in a CJK (Asian characters) workdir."""
    cjk_dir = tmp_path / "東京_Tokyo_2026"
    ws, hosts, req, leases = create_unicode_world(cjk_dir)

    code = (
        "import pathlib; "
        "pathlib.Path('データ_result.json').write_bytes(b'{\"status\": \"ok\", \"cjk\": true}')"
    )
    step = Step("step_cjk", [sys.executable, "-c", code], "データ_result.json")

    try:
        result = ws.run("wk-cjk", Requirement(frozenset({"python"})), "project:p1", req, [step], host=hosts[0])
        assert result["state"] == "DONE"

        out_file = cjk_dir / "データ_result.json"
        assert out_file.exists()
        assert b"ok" in out_file.read_bytes()

        facts = ws.log.facts("wk-cjk")
        assert len(facts) == 1
        assert "データ_result.json" in facts[0].statement
    finally:
        leases.close()


def test_positive_verbatim_unicode_workdir(tmp_path):
    """Windows verbatim path (\\\\?\\) pointing to a Unicode workdir executes cleanly."""
    raw_dir = tmp_path / "Verbatim_München_2026"
    raw_dir.mkdir(parents=True, exist_ok=True)
    verbatim_dir = Path(f"\\\\?\\{str(raw_dir)}")

    ws, hosts, req, leases = create_unicode_world(verbatim_dir)

    code = "import pathlib; pathlib.Path('verbatim_out.log').write_bytes(b'verbatim_unicode_ok')"
    step = Step("step_verbatim", [sys.executable, "-c", code], "verbatim_out.log")

    try:
        result = ws.run("wk-verbatim", Requirement(frozenset({"python"})), "project:p1", req, [step], host=hosts[0])
        assert result["state"] == "DONE"
        assert (raw_dir / "verbatim_out.log").exists()
    finally:
        leases.close()


def test_positive_authentic_root_discovery_in_unicode_hierarchy(tmp_path):
    """Authentic workspace root discovery traverses upwards through Unicode directory levels."""
    repo_root = tmp_path / "Über_Courier_Projekt_2026"
    nested = repo_root / "unterordner_äö" / "tiefes_modul"
    nested.mkdir(parents=True)
    (repo_root / ".git").mkdir()
    (repo_root / "pyproject.toml").touch()

    discovered = find_authentic_workspace_root(start_path=nested)
    assert discovered == repo_root.resolve()

    valid, details = verify_workspace_root(nested, expected_name="Über_Courier_Projekt_2026")
    assert valid is True
    assert details == str(repo_root.resolve())


def test_negative_path_escaping_unicode_workdir_rejected(tmp_path):
    """Boundary confinement prevents breakout from a Unicode workspace."""
    u_dir = tmp_path / "München_2026"
    ws, hosts, req, leases = create_unicode_world(u_dir)

    # 1. Traversal relative
    assert resolve_workspace_child(u_dir, "../outside.txt") is None

    # 2. Sibling directory with shared prefix
    sibling = str(u_dir) + "_attacker"
    assert resolve_workspace_child(u_dir, f"{sibling}/file.txt") is None

    # 3. Workspace execution fails closed when step attempts to escape
    escaping_step = Step("malicious", [sys.executable, "-c", "pass"], "../escaped.txt")
    try:
        result = ws.run("wk-escape", Requirement(frozenset({"python"})), "project:p1", req, [escaping_step], host=hosts[0])
        assert result["state"] == "FAILED"
        assert any("escapes workdir" in r for r in result["reasons"])
    finally:
        leases.close()


def test_cli_verify_workspace_root_in_unicode_path_subprocess(tmp_path):
    """CLI subprocess tool validates authentic root when path contains Unicode."""
    py = sys.executable
    script = os.path.join("scripts", "verify_workspace_root.py")

    repo_root = tmp_path / "München_Root_2026"
    deep = repo_root / "sub" / "leaf"
    deep.mkdir(parents=True)
    (repo_root / "pyproject.toml").touch()

    proc = subprocess.run([py, script, "--path", str(deep), "--expected-name", "München_Root_2026"], capture_output=True, text=True)
    assert proc.returncode == 0
    assert "AUTHENTIC WORKSPACE ROOT: " in proc.stdout
    assert "München_Root_2026" in proc.stdout
