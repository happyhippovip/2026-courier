import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

from scripts.mac_worker.status import derive_status, parse_launchctl_dict

ROOT = Path(__file__).resolve().parents[1]
STATUS_PY = ROOT / "scripts/mac_worker/status.py"
STATUS_SH = ROOT / "scripts/mac_worker/status.sh"
INSTALL_SH = ROOT / "scripts/mac_worker/install.sh"
START_SH = ROOT / "scripts/mac_worker/start.sh"
STOP_SH = ROOT / "scripts/mac_worker/stop.sh"


def test_parse_launchctl_dict():
    sample = """{
\t"Label" = "com.courier.mac_worker";
\t"LimitLoadToSessionType" = "Aqua";
\t"OnDemand" = true;
\t"LastExitStatus" = 0;
\t"PID" = 12345;
\t"Program" = "/usr/local/bin/python3";
};"""
    parsed = parse_launchctl_dict(sample)
    assert parsed["Label"] == "com.courier.mac_worker"
    assert parsed["PID"] == 12345
    assert parsed["LastExitStatus"] == 0
    assert parsed["Program"] == "/usr/local/bin/python3"


def test_derive_status_not_installed(tmp_path):
    missing_plist = tmp_path / "nonexistent.plist"
    res = derive_status(plist_path=missing_plist, here_dir=tmp_path)
    assert res["status"] == "NOT_INSTALLED"
    assert res["plist_exists"] is False
    assert res["launchctl_loaded"] is False


def test_derive_status_installed_not_loaded(tmp_path, monkeypatch):
    plist = tmp_path / "com.courier.mac_worker.plist"
    plist.write_text("<plist></plist>")
    
    # Mock query_launchctl to return not loaded
    import scripts.mac_worker.status as st
    monkeypatch.setattr(st, "query_launchctl", lambda label: {"loaded": False, "pid": None, "last_exit_status": None, "raw": "not found"})
    
    res = derive_status(plist_path=plist, here_dir=tmp_path)
    assert res["status"] == "INSTALLED_NOT_LOADED"
    assert res["plist_exists"] is True
    assert res["launchctl_loaded"] is False


def test_derive_status_running(tmp_path, monkeypatch):
    plist = tmp_path / "com.courier.mac_worker.plist"
    plist.write_text("<plist></plist>")
    
    import scripts.mac_worker.status as st
    monkeypatch.setattr(st, "query_launchctl", lambda label: {"loaded": True, "pid": 9876, "last_exit_status": 0, "raw": ""})
    
    res = derive_status(plist_path=plist, here_dir=tmp_path)
    assert res["status"] == "RUNNING"
    assert res["pid"] == 9876
    assert res["launchctl_loaded"] is True


def test_derive_status_loaded_stopped(tmp_path, monkeypatch):
    plist = tmp_path / "com.courier.mac_worker.plist"
    plist.write_text("<plist></plist>")
    
    import scripts.mac_worker.status as st
    monkeypatch.setattr(st, "query_launchctl", lambda label: {"loaded": True, "pid": None, "last_exit_status": 1, "raw": ""})
    
    res = derive_status(plist_path=plist, here_dir=tmp_path)
    assert res["status"] == "LOADED_STOPPED"
    assert res["pid"] is None
    assert res["last_exit_status"] == 1


def test_status_cli_json_output(tmp_path):
    plist = tmp_path / "test.plist"
    cmd = [sys.executable, str(STATUS_PY), "--json", "--plist-path", str(plist)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    assert p.returncode == 1  # NOT_INSTALLED exits 1
    data = json.loads(p.stdout)
    assert data["status"] == "NOT_INSTALLED"
    assert data["plist_exists"] is False


def test_no_grep_family_in_mac_worker_scripts():
    """Verify that none of the mac_worker scripts invoke grep/egrep/fgrep/rg commands."""
    scripts_dir = ROOT / "scripts/mac_worker"
    forbidden_cmd_patterns = ["grep ", "| grep", "grep -", "egrep ", "| egrep", "fgrep ", "| fgrep", "ripgrep ", "rg "]
    for f in scripts_dir.iterdir():
        if f.suffix in (".sh", ".py", ".bash"):
            for line in f.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue  # Skip comments
                for forb in forbidden_cmd_patterns:
                    assert forb not in stripped.lower(), f"Forbidden search command '{forb}' invoked in {f.name}: {line}"


def test_install_script_fails_closed_when_launchctl_list_fails(tmp_path):
    """Test that install.sh fails if launchctl list cannot verify registration."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    # Mock launchctl: load succeeds (exit 0), but list fails (exit 113)
    launchctl_script = """#!/bin/sh
if [ "$1" = "load" ]; then
    exit 0
elif [ "$1" = "list" ]; then
    exit 113
fi
exit 0
"""
    (bindir / "launchctl").write_text(launchctl_script)
    (bindir / "launchctl").chmod(0o755)

    env = {"PATH": f"{bindir}:/usr/bin:/bin", "HOME": str(tmp_path)}
    r = subprocess.run(["bash", str(INSTALL_SH)], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert r.returncode != 0
    assert "not registered in launchctl" in r.stderr.lower() or "failed" in r.stderr.lower()
