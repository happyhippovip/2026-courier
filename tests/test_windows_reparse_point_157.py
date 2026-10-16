"""Deterministic and isolated tests for Windows Reparse Point Security (SEED 157).

MISSION: WINDOWS-REPARSE-POINT ABSICHERN.
Verifies authentic detection, containment verification, escape prevention,
TOCTOU post-execution checks, and CLI auditing for NTFS directory junctions
and symbolic links.
"""
import os
from pathlib import Path
import subprocess
import sys
import pytest

from courier_runtime.workspace import (
    Workspace,
    Step,
    is_reparse_point,
    is_path_confined,
    find_reparse_points_in_path,
    check_reparse_point_safety,
    resolve_workspace_child,
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


def create_world(workdir_path):
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


def _create_junction(link_path: Path, target_path: Path) -> bool:
    """Helper creating an NTFS directory junction on Windows."""
    if os.name != "nt":
        try:
            link_path.symlink_to(target_path, target_is_directory=True)
            return True
        except OSError:
            return False
    res = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link_path), str(target_path)],
        capture_output=True,
        text=True,
    )
    return res.returncode == 0


def test_is_reparse_point_detection(tmp_path):
    """Testet die verlässliche Erkennung von Windows NTFS Reparse Points."""
    regular_dir = tmp_path / "regular_dir"
    regular_dir.mkdir()
    regular_file = regular_dir / "regular.txt"
    regular_file.write_text("hello")

    assert is_reparse_point(regular_dir) is False
    assert is_reparse_point(regular_file) is False
    assert is_reparse_point(tmp_path / "nonexistent") is False
    assert is_reparse_point(None) is False
    assert is_reparse_point("") is False

    # Erstelle eine echte Directory Junction
    junc_dir = tmp_path / "junc_dir"
    created = _create_junction(junc_dir, regular_dir)
    if not created:
        pytest.skip("NTFS Junction creation failed or not supported in this test runner")

    try:
        assert is_reparse_point(junc_dir) is True
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(junc_dir)], capture_output=True)


def test_is_path_confined_boundaries(tmp_path):
    """Prüft die Begrenzung von Pfaden innerhalb eines Workspace-Roots."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    child = ws / "subdir" / "data.txt"

    assert is_path_confined(child, ws) is True
    assert is_path_confined(ws, ws) is True
    assert is_path_confined(tmp_path / "outside.txt", ws) is False
    assert is_path_confined(r"D:\other_drive\file.txt", ws) is False


def test_find_reparse_points_in_path_hierarchy(tmp_path):
    """Prüft das Auffinden von Reparse-Points entlang der Verzeichnishierarchie."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    target = tmp_path / "target_folder"
    target.mkdir()

    junc = ws / "junction_node"
    created = _create_junction(junc, target)
    if not created:
        pytest.skip("NTFS Junction creation failed")

    nested_file = junc / "deep" / "file.txt"

    try:
        found = find_reparse_points_in_path(nested_file, stop_at=ws)
        assert len(found) >= 1
        assert any(p.name == "junction_node" for p in found)

        # Für reguläre Pfade dürfen keine Reparse-Points gemeldet werden
        regular_nested = ws / "regular_sub" / "file.txt"
        assert len(find_reparse_points_in_path(regular_nested, stop_at=ws)) == 0
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(junc)], capture_output=True)


def test_check_reparse_point_safety_contract(tmp_path):
    """Prüft den formellen Sicherheitsvertrag von check_reparse_point_safety."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    inside_dir = ws / "internal_storage"
    inside_dir.mkdir()
    outside_dir = tmp_path / "outside_storage"
    outside_dir.mkdir()

    # Fall 1: Regulärer Pfad ohne Reparse Points
    ok1, msg1 = check_reparse_point_safety(inside_dir / "file.txt", workdir=ws)
    assert ok1 is True
    assert msg1 == "NO_REPARSE_POINT"

    # Fall 2: Confined Junction (zeigt auf Ordner innerhalb von ws)
    confined_junc = ws / "internal_junc"
    if not _create_junction(confined_junc, inside_dir):
        pytest.skip("NTFS Junction creation failed")

    try:
        ok2, msg2 = check_reparse_point_safety(confined_junc, workdir=ws, allow_confined=True)
        assert ok2 is True
        assert "CONFINED_REPARSE_POINT" in msg2

        # Confined Junction abweisen, wenn Policy Reparse-Points komplett verbietet
        ok_disallow, msg_disallow = check_reparse_point_safety(confined_junc, workdir=ws, allow_confined=False)
        assert ok_disallow is False
        assert "REPARSE_POINT_DISALLOWED" in msg_disallow
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(confined_junc)], capture_output=True)

    # Fall 3: Unconfined Junction (Ausbruch aus dem Workspace)
    escape_junc = ws / "escape_junc"
    if not _create_junction(escape_junc, outside_dir):
        pytest.skip("NTFS Junction creation failed")

    try:
        ok3, msg3 = check_reparse_point_safety(escape_junc / "secret.txt", workdir=ws)
        assert ok3 is False
        assert "REPARSE_POINT_ESCAPE" in msg3
        assert "outside authorized workdir" in msg3
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(escape_junc)], capture_output=True)


def test_resolve_workspace_child_rejects_escaping_reparse_point(tmp_path):
    """resolve_workspace_child liefert None bei Reparse-Points, die aus dem Workspace ausbrechen."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    outside = tmp_path / "secret_zone"
    outside.mkdir()

    leak_junc = ws / "leak_junc"
    if not _create_junction(leak_junc, outside):
        pytest.skip("NTFS Junction creation failed")

    try:
        # Ausbruchspfad über Junction muss None liefern
        assert resolve_workspace_child(ws, "leak_junc/data.txt") is None
        assert resolve_workspace_child(ws, str(leak_junc / "data.txt")) is None

        # Regulärer Pfad bleibt auflösbar
        assert resolve_workspace_child(ws, "regular.txt") is not None
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(leak_junc)], capture_output=True)


def test_workspace_execution_refuses_escaping_reparse_output(tmp_path):
    """Workspace.run blockiert Schritte vorab, wenn der deklarierte Output über einen Reparse Point entweicht."""
    ws_dir = tmp_path / "workspace"
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    ws, hosts, req, leases = create_world(ws_dir)

    junc = ws_dir / "exploit_link"
    if not _create_junction(junc, outside_dir):
        leases.close()
        pytest.skip("NTFS Junction creation failed")

    bad_step = Step(
        name="reparse-exploit",
        argv=[sys.executable, "-c", "import sys; sys.exit(0)"],
        output="exploit_link/payload.txt",
    )

    try:
        res = ws.run("wk-rp-fail", Requirement(frozenset({"python"})), "workspace:p1", req, [bad_step], host=hosts[0])
        assert res["state"] == "FAILED"
        assert "output path escapes workdir" in res["reasons"][0]
        assert len(ws.evidence) == 0
    finally:
        leases.close()
        subprocess.run(["cmd", "/c", "rmdir", str(junc)], capture_output=True)


def test_workspace_execution_post_check_catches_planted_reparse_output(tmp_path):
    """TOCTOU-Schutz: Wenn der Kindprozess während der Ausführung eine Junction als Output platziert, schlägt die Verifikation fehl."""
    ws_dir = tmp_path / "workspace"
    outside_dir = tmp_path / "outside_system"
    outside_dir.mkdir()
    (outside_dir / "target.txt").write_text("external confidential")

    ws, hosts, req, leases = create_world(ws_dir)

    # Der Prozess erstellt während der Ausführung eine Junction 'planted_output' nach outside_dir
    script = (
        f"import subprocess, sys\n"
        f"subprocess.run(['cmd', '/c', 'mklink', '/J', 'planted_output', {repr(str(outside_dir))}])\n"
        f"sys.exit(0)\n"
    )

    step = Step(
        name="plant-reparse-step",
        argv=[sys.executable, "-c", script],
        output="planted_output",
    )

    try:
        res = ws.run("wk-toctou-rp", Requirement(frozenset({"python"})), "workspace:p1", req, [step], host=hosts[0])
        assert res["state"] == "FAILED"
        assert "output violates reparse point security" in res["reasons"][0]
        assert "REPARSE_POINT_ESCAPE" in res["reasons"][0]
        # Keine Evidenz für das fremde Verzeichnis/Datei akzeptiert
        assert len(ws.evidence) == 0
    finally:
        leases.close()
        subprocess.run(["cmd", "/c", "rmdir", str(ws_dir / "planted_output")], capture_output=True)


def test_cli_verify_reparse_point(tmp_path):
    """Testet das CLI-Werkzeug scripts/verify_reparse_point.py per Subprozess."""
    script_path = Path(__file__).parent.parent / "scripts" / "verify_reparse_point.py"
    assert script_path.exists(), f"CLI script {script_path} must exist"

    ws = tmp_path / "workspace"
    ws.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    # Fall 1: Regulärer Pfad -> Exit Code 0
    reg_file = ws / "regular.txt"
    reg_file.write_text("ok")
    res_reg = subprocess.run(
        [sys.executable, str(script_path), str(reg_file), "--workdir", str(ws)],
        capture_output=True,
        text=True,
    )
    assert res_reg.returncode == 0
    assert "REPARSE POINT SAFE" in res_reg.stdout
    assert "NO_REPARSE_POINT" in res_reg.stdout

    # Fall 2: Escaping Junction -> Exit Code 1
    bad_junc = ws / "bad_junc"
    if not _create_junction(bad_junc, outside):
        pytest.skip("NTFS Junction creation failed")

    try:
        res_esc = subprocess.run(
            [sys.executable, str(script_path), str(bad_junc), "--workdir", str(ws)],
            capture_output=True,
            text=True,
        )
        assert res_esc.returncode == 1
        assert "REPARSE POINT REFUSED" in res_esc.stdout
        assert "REPARSE_POINT_ESCAPE" in res_esc.stdout

        # Fall 3: Disallow-All -> Exit Code 1
        inside = ws / "inside_sub"
        inside.mkdir()
        good_junc = ws / "good_junc"
        if _create_junction(good_junc, inside):
            try:
                res_disallow = subprocess.run(
                    [sys.executable, str(script_path), str(good_junc), "--workdir", str(ws), "--disallow-all"],
                    capture_output=True,
                    text=True,
                )
                assert res_disallow.returncode == 1
                assert "REPARSE_POINT_DISALLOWED" in res_disallow.stdout
            finally:
                subprocess.run(["cmd", "/c", "rmdir", str(good_junc)], capture_output=True)
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(bad_junc)], capture_output=True)

    # Fall 4: Parameter fehlt -> Exit Code 2
    res_err = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True)
    assert res_err.returncode == 2
