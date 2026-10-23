import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

from scripts.mac_worker.status import derive_status, parse_launchctl_dict, query_worker_state

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


def test_state_files_do_not_follow_a_symlink(tmp_path):
    outside_task = tmp_path / "outside-task.json"
    outside_task.write_text(json.dumps({
        "task_id": "SECRET-TASK",
        "worker_phase": "run",
        "dispatch_id": "SECRET-DISPATCH",
    }), encoding="utf-8")
    outside_ckpt = tmp_path / "outside-ckpt.json"
    outside_ckpt.write_text(json.dumps({
        "task_id": "SECRET-CKPT",
        "phase": "x",
        "branch": "SECRET-BRANCH",
    }), encoding="utf-8")
    here = tmp_path / "here"
    state = here / "state"
    state.mkdir(parents=True)
    (state / "current_task.json").symlink_to(outside_task)
    (state / "checkpoint.json").symlink_to(outside_ckpt)

    parent_real = tmp_path / "parent-real"
    parent_real.mkdir()
    (parent_real / "current_task.json").write_text(json.dumps({
        "task_id": "SECRET-PARENT",
        "worker_phase": "parent",
        "dispatch_id": "d",
    }), encoding="utf-8")
    parent_here = tmp_path / "parent-here"
    parent_here.mkdir()
    (parent_here / "state").symlink_to(parent_real)

    plain = tmp_path / "plain"
    plain_state = plain / "state"
    plain_state.mkdir(parents=True)
    (plain_state / "current_task.json").write_text(json.dumps({
        "task_id": "PLAIN-TASK",
        "worker_phase": "idle",
        "dispatch_id": "plain-d",
    }), encoding="utf-8")

    def run(dest):
        try:
            return query_worker_state(dest), None
        except ValueError as exc:
            return None, str(exc)

    got_link, err_link = run(here)
    got_parent, err_parent = run(parent_here)
    got_plain, err_plain = run(plain)
    refused = "refusing to follow a symlink"
    assert (
        err_link == refused and got_link is None
        and err_parent == refused and got_parent is None
        and err_plain is None and got_plain["task_id"] == "PLAIN-TASK"
        and (state / "current_task.json").is_symlink()
        and (parent_here / "state").is_symlink()
    ), (got_link, err_link, got_parent, err_parent, got_plain, err_plain)

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


def test_bool_pid_is_not_running(tmp_path, monkeypatch):
    plist = tmp_path / "com.courier.mac_worker.plist"
    plist.write_text("<plist></plist>")
    import scripts.mac_worker.status as st

    def run(pid):
        monkeypatch.setattr(
            st,
            "query_launchctl",
            lambda label, pid=pid: {
                "loaded": True,
                "pid": pid,
                "last_exit_status": 0,
                "raw": "",
            },
        )
        try:
            res = derive_status(plist_path=plist, here_dir=tmp_path)
        except ValueError as exc:
            return ("err", str(exc))
        return ("ok", res["status"], res["pid"])

    true_result = run(True)
    false_result = run(False)
    int_result = run(5)
    assert (true_result, false_result, int_result) == (
        ("err", "Bool is not a number."),
        ("err", "Bool is not a number."),
        ("ok", "RUNNING", 5),
    )


def test_bool_exit_status_is_not_a_code(tmp_path, monkeypatch):
    plist = tmp_path / "com.courier.mac_worker.plist"
    plist.write_text("<plist></plist>")
    import scripts.mac_worker.status as st

    def run(code):
        monkeypatch.setattr(
            st,
            "query_launchctl",
            lambda label, code=code: {
                "loaded": True,
                "pid": 5,
                "last_exit_status": code,
                "raw": "",
            },
        )
        try:
            res = derive_status(plist_path=plist, here_dir=tmp_path)
        except ValueError as exc:
            return ("err", str(exc))
        return ("ok", res["status"], res["pid"], res["last_exit_status"])

    assert (run(True), run(False), run(0)) == (
        ("err", "Bool is not a number."),
        ("err", "Bool is not a number."),
        ("ok", "RUNNING", 5, 0),
    )


def test_plist_does_not_follow_a_symlink(tmp_path, monkeypatch):
    import scripts.mac_worker.status as st

    monkeypatch.setattr(
        st,
        "query_launchctl",
        lambda label: {
            "loaded": False,
            "pid": None,
            "last_exit_status": None,
            "raw": "",
        },
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    real = outside / "real.plist"
    real.write_text("OUTSIDE-PLIST")
    link = tmp_path / "linked.plist"
    link.symlink_to(real)

    parent_outside = tmp_path / "parent-outside"
    parent_outside.mkdir()
    (parent_outside / "agent.plist").write_text("PARENT-PLIST")
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(parent_outside, target_is_directory=True)
    parent_plist = linked_parent / "agent.plist"

    plain = tmp_path / "plain.plist"
    plain.write_text("<plist></plist>")

    def run(path):
        try:
            res = derive_status(plist_path=path, here_dir=tmp_path)
        except ValueError as exc:
            return ("err", str(exc))
        return ("ok", res["status"], res["plist_exists"])

    assert (run(link), run(parent_plist), run(plain)) == (
        ("err", "refusing to follow a symlink"),
        ("err", "refusing to follow a symlink"),
        ("ok", "INSTALLED_NOT_LOADED", True),
    )


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
