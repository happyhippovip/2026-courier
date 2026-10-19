"""The Muse night uninstaller must not report removal while the plist remains."""

import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "uninstall_macos_muse_night_runner.sh"
LABEL = "com.couriersymphony.dev.muse-night"
REMOVED = f"Removed launchd job: {LABEL}"


def _bind(base: Path, uname_text: str, launchctl: str | None) -> Path:
    bind = base / "bin"
    bind.mkdir()
    for src in (Path("/bin"), Path("/usr/bin")):
        if not src.is_dir():
            continue
        for child in src.iterdir():
            if child.name in {"launchctl", "uname"} or not child.exists():
                continue
            dest = bind / child.name
            if dest.exists():
                continue
            dest.symlink_to(child)
    uname = bind / "uname"
    uname.write_text(f"#!/bin/sh\necho {uname_text}\n", encoding="utf-8")
    uname.chmod(uname.stat().st_mode | stat.S_IXUSR)
    if launchctl is not None:
        exe = bind / "launchctl"
        exe.write_text(launchctl, encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    return bind


def _case(tmp_path: Path, name: str, uname_text: str, launchctl: str | None = None, bootout_rc: int = 0):
    base = tmp_path / name
    home = base / "home"
    plist = home / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    plist.parent.mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = str(_bind(base, uname_text, launchctl))
    env["BOOTOUT_RC"] = str(bootout_rc)
    env["LAUNCHCTL_LOG"] = str(base / "launchctl.log")
    return env, plist


def _run(env: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_non_darwin_does_not_report_removal(tmp_path):
    env, plist = _case(tmp_path, "linux", "Linux")
    proc = _run(env)
    assert proc.returncode == 64
    assert REMOVED not in proc.stdout
    assert not plist.exists()


def test_failed_removal_is_not_removed(tmp_path):
    env, plist = _case(tmp_path, "dir", "Darwin")
    plist.mkdir()
    proc = _run(env)
    assert proc.returncode != 0
    assert REMOVED not in proc.stdout
    assert "not proven" in proc.stderr
    assert plist.is_dir()


def test_file_plist_is_removed_without_launchctl(tmp_path):
    env, plist = _case(tmp_path, "file", "Darwin")
    plist.write_text("plist", encoding="utf-8")
    proc = _run(env)
    assert proc.returncode == 0, proc.stderr
    assert REMOVED in proc.stdout
    assert not plist.exists()


def test_missing_plist_is_already_absent(tmp_path):
    env, plist = _case(tmp_path, "missing", "Darwin")
    proc = _run(env)
    assert proc.returncode == 0, proc.stderr
    assert REMOVED in proc.stdout
    assert not plist.exists()


def test_failed_bootout_leaves_the_plist(tmp_path):
    stub = """#!/bin/sh
printf '%s\\n' "$*" >> "$LAUNCHCTL_LOG"
exit "${BOOTOUT_RC:-0}"
"""
    env, plist = _case(tmp_path, "boot", "Darwin", launchctl=stub, bootout_rc=1)
    plist.write_text("still", encoding="utf-8")
    proc = _run(env)
    assert proc.returncode != 0
    assert REMOVED not in proc.stdout
    assert plist.read_text(encoding="utf-8") == "still"
    log = (tmp_path / "boot" / "launchctl.log").read_text(encoding="utf-8")
    assert "bootout" in log
