"""setup_local_autonomy.sh must not report services running when launchctl did not load them."""

import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "setup_local_autonomy.sh"
SUCCESS = "Vollautomatik Background Services installed and running!"


def _path_without_real_launchctl(tmp_path: Path, stub: str | None = None) -> Path:
    bind = tmp_path / "bin"
    bind.mkdir()
    for src in (Path("/bin"), Path("/usr/bin")):
        if not src.is_dir():
            continue
        for child in src.iterdir():
            if child.name == "launchctl" or not child.exists():
                continue
            dest = bind / child.name
            if dest.exists():
                continue
            dest.symlink_to(child)
    if stub is not None:
        exe = bind / "launchctl"
        exe.write_text(stub, encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    return bind


def _run(tmp_path: Path, *, keys: bool, stub: str | None = None, fail_load: bool = False):
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = str(_path_without_real_launchctl(tmp_path, stub))
    if keys:
        env["COURIER_API_KEY"] = "dummy-not-a-secret"
        env["COURIER_VERIFIER_API_KEY"] = "dummy-verifier"
    else:
        env.pop("COURIER_API_KEY", None)
        env.pop("COURIER_VERIFIER_API_KEY", None)
    env["FAIL_LOAD"] = "1" if fail_load else "0"
    env["LAUNCHCTL_LOG"] = str(tmp_path / "launchctl.log")
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    return proc, home


def test_missing_launchctl_is_not_running(tmp_path):
    proc, home = _run(tmp_path, keys=True, stub=None)
    assert proc.returncode != 0
    assert SUCCESS not in proc.stdout
    assert "not proven" in proc.stderr
    agents = home / "Library" / "LaunchAgents"
    assert not agents.exists() or list(agents.iterdir()) == []


def test_failed_load_is_not_running(tmp_path):
    stub = """#!/bin/sh
printf '%s\\n' "$*" >> "$LAUNCHCTL_LOG"
if [ "$1" = "load" ] && [ "${FAIL_LOAD:-0}" = "1" ]; then
  echo "load failed" >&2
  exit 1
fi
exit 0
"""
    proc, home = _run(tmp_path, keys=True, stub=stub, fail_load=True)
    assert proc.returncode != 0
    assert SUCCESS not in proc.stdout
    assert "not proven" in proc.stderr
    assert not (home / "Library" / "LaunchAgents" / "com.courier.mac_worker.plist").exists()


def test_successful_load_reports_running(tmp_path):
    stub = """#!/bin/sh
printf '%s\\n' "$*" >> "$LAUNCHCTL_LOG"
exit 0
"""
    proc, home = _run(tmp_path, keys=True, stub=stub, fail_load=False)
    assert proc.returncode == 0, proc.stderr
    assert SUCCESS in proc.stdout
    assert (home / "Library" / "LaunchAgents" / "com.courier.server.plist").is_file()
    assert (home / "Library" / "LaunchAgents" / "com.courier.mac_worker.plist").is_file()


def test_missing_keys_make_no_changes(tmp_path):
    proc, home = _run(tmp_path, keys=False, stub=None)
    assert proc.returncode != 0
    assert SUCCESS not in proc.stdout
    assert not (home / "Library").exists()
