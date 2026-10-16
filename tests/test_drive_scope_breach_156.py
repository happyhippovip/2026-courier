"""Deterministic and isolated tests for Drive Scope Breach Detection (SEED 156).

MISSION: LAUFWERKSWECHSEL ALS SCOPEBRUCH PRÜFEN.
Verifies authentic detection and rejection of cross-drive paths, drive-relative
path escapes, UNC redirections, and Windows verbatim cross-drive targets.
"""
import os
from pathlib import Path
import subprocess
import sys
import pytest

from courier_runtime.workspace import (
    Workspace,
    Step,
    extract_windows_drive,
    is_drive_scope_breach,
    check_drive_scope,
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


def test_extract_windows_drive_variations():
    """Prüft das sichere Extrahieren von Laufwerksbuchstaben und UNC-Hosts."""
    assert extract_windows_drive(r"C:\workspace\data.txt") == "C:"
    assert extract_windows_drive("c:/workspace/data.txt") == "C:"
    assert extract_windows_drive(r"d:\other\drive.dat") == "D:"
    assert extract_windows_drive(r"D:relative.txt") == "D:"
    assert extract_windows_drive(r"\\?\C:\workspace\data.txt") == "C:"
    assert extract_windows_drive(r"\\?\D:\external\file.bin") == "D:"
    assert extract_windows_drive(r"\\SERVER01\share\sub\file.txt") == r"\\SERVER01"
    assert extract_windows_drive(r"\\?\UNC\SERVER02\share\sub\file.txt") == r"\\SERVER02"
    assert extract_windows_drive("relative/path/only.txt") is None
    assert extract_windows_drive("") is None
    assert extract_windows_drive(None) is None


def test_is_drive_scope_breach_detection():
    """Prüft die Erkennung von unautorisierten Laufwerks- und Host-Wechseln."""
    # Selbes Laufwerk: Kein Bruch
    assert not is_drive_scope_breach(r"C:\workdir", r"C:\workdir\output.txt")
    assert not is_drive_scope_breach(r"C:\workdir", r"subfolder\output.txt")
    assert not is_drive_scope_breach(r"C:\workdir", r"C:\workdir\..\workdir\output.txt")

    # Anderes Laufwerk: Konkreter Bruch
    assert is_drive_scope_breach(r"C:\workdir", r"D:\output.txt")
    assert is_drive_scope_breach(r"C:\workdir", r"D:relative.txt")
    assert is_drive_scope_breach(r"C:\workdir", r"E:\temp\leak.log")
    assert is_drive_scope_breach(r"C:\workdir", r"\\?\D:\verbatim\breach.bin")

    # Lokales Laufwerk nach UNC Netzwerkpfad: Bruch
    assert is_drive_scope_breach(r"C:\workdir", r"\\REMOTE_SERVER\share\file.txt")
    assert is_drive_scope_breach(r"C:\workdir", r"\\?\UNC\REMOTE_SERVER\share\file.txt")

    # Unterschiedliche UNC-Shares: Bruch
    assert is_drive_scope_breach(r"\\SERVER1\share", r"\\SERVER2\share\file.txt")
    # Gleiche UNC-Share: Kein Bruch
    assert not is_drive_scope_breach(r"\\SERVER1\share", r"\\SERVER1\share\data.txt")


def test_check_drive_scope_contract():
    """Prüft den formellen Vertrag von check_drive_scope."""
    ok, msg = check_drive_scope(r"C:\courier_ws", r"C:\courier_ws\results\res.json")
    assert ok is True
    assert msg == "VALID_DRIVE_SCOPE"

    fail, reason = check_drive_scope(r"C:\courier_ws", r"D:\courier_ws\results\res.json")
    assert fail is False
    assert "DRIVE_SCOPE_BREACH" in reason
    assert "target drive 'D:' differs from authorized workspace drive 'C:'" in reason

    fail_unc, unc_reason = check_drive_scope(r"C:\courier_ws", r"\\EXFILTRATION\drop\res.json")
    assert fail_unc is False
    assert "DRIVE_SCOPE_BREACH" in unc_reason
    assert r"target drive '\\EXFILTRATION'" in unc_reason


def test_resolve_workspace_child_rejects_foreign_drives():
    """Prüft, dass resolve_workspace_child fremde Laufwerke strikt abweist (None)."""
    ws = r"C:\Users\lol\courier_ws"

    # Gültige relative Pfade
    res = resolve_workspace_child(ws, "child.txt")
    assert res is not None
    assert str(res).lower().endswith("child.txt")

    # Fremde Laufwerke müssen None liefern (Fail-Closed)
    assert resolve_workspace_child(ws, r"D:\escape.txt") is None
    assert resolve_workspace_child(ws, r"D:drive_relative.txt") is None
    assert resolve_workspace_child(ws, r"Z:\secret.key") is None
    assert resolve_workspace_child(ws, r"\\?\D:\verbatim_escape.txt") is None
    assert resolve_workspace_child(ws, r"\\corp_share\public\escape.txt") is None


def test_workspace_execution_refuses_cross_drive_step_output(tmp_path):
    """Prüft, dass Workspace.run Schritte mit Cross-Drive-Output sofort blockiert."""
    workdir = tmp_path / "authorized_workspace"
    ws, hosts, req, leases = create_world(workdir)

    # Schritt 1: Versucht, auf ein fremdes Laufwerk (z.B. X:\out.txt) zu schreiben
    foreign_output = r"X:\rogue_output\result.txt"
    bad_step = Step(
        name="cross-drive-exploit",
        argv=[sys.executable, "-c", "import sys; sys.exit(0)"],
        output=foreign_output,
    )

    try:
        result = ws.run(
            "wk_scope_breach_test",
            Requirement(frozenset({"python"})),
            "workspace:p1",
            req,
            [bad_step],
            host=hosts[0],
        )

        assert result["state"] == "FAILED"
        assert "output path escapes workdir" in result["reasons"][0]
        assert foreign_output in result["reasons"][0]
        # Keine Evidenzen erzeugt
        assert len(ws.evidence) == 0
    finally:
        leases.close()


def test_workspace_execution_succeeds_for_conforming_drive_step(tmp_path):
    """Positivtest: Schritt innerhalb des autorisierten Workspace-Laufwerks läuft erfolgreich durch."""
    workdir = tmp_path / "valid_workspace"
    ws, hosts, req, leases = create_world(workdir)

    out_rel = "artifact.txt"
    code = f"import pathlib; pathlib.Path('{out_rel}').write_bytes(b'authorized')"
    good_step = Step(
        name="valid-drive-step",
        argv=[sys.executable, "-c", code],
        output=out_rel,
    )

    try:
        result = ws.run(
            "wk_valid_drive_test",
            Requirement(frozenset({"python"})),
            "workspace:p1",
            req,
            [good_step],
            host=hosts[0],
        )

        assert result["state"] == "DONE"
        assert len(ws.evidence) == 1
        assert ws.evidence[0].passed is True
        assert (workdir / out_rel).exists()
        assert (workdir / out_rel).read_bytes() == b"authorized"
    finally:
        leases.close()


def test_cli_verify_drive_scope():
    """Testet das CLI-Werkzeug scripts/verify_drive_scope.py isoliert per Subprozess."""
    script_path = Path(__file__).parent.parent / "scripts" / "verify_drive_scope.py"
    assert script_path.exists(), f"CLI tool {script_path} must exist"

    # Fall 1: Positiv - gleiches Laufwerk
    res_pos = subprocess.run(
        [sys.executable, str(script_path), "--workdir", r"C:\workspace", r"C:\workspace\sub\out.txt"],
        capture_output=True,
        text=True,
    )
    assert res_pos.returncode == 0
    assert "DRIVE SCOPE VALID" in res_pos.stdout

    # Fall 2: Negativ - fremdes Laufwerk D:
    res_neg = subprocess.run(
        [sys.executable, str(script_path), "--workdir", r"C:\workspace", r"D:\external\out.txt"],
        capture_output=True,
        text=True,
    )
    assert res_neg.returncode == 1
    assert "DRIVE SCOPE FAILED (BREACH)" in res_neg.stdout
    assert "DRIVE_SCOPE_BREACH" in res_neg.stdout

    # Fall 3: Negativ - UNC-Netzwerkpfad gegen lokales Laufwerk C:
    res_unc = subprocess.run(
        [sys.executable, str(script_path), "--workdir", r"C:\workspace", r"\\remote_host\share\out.txt"],
        capture_output=True,
        text=True,
    )
    assert res_unc.returncode == 1
    assert "DRIVE SCOPE FAILED (BREACH)" in res_unc.stdout
    assert r"target drive '\\REMOTE_HOST'" in res_unc.stdout

    # Fall 4: Fehler bei fehlendem Argument
    res_err = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
    )
    assert res_err.returncode == 2
